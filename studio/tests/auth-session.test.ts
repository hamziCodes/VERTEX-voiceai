import { beforeEach, describe, expect, it, vi } from "vitest";

const withAuth = vi.fn();

vi.mock("@workos-inc/authkit-nextjs", () => ({ withAuth }));

describe("Studio WorkOS session boundary", () => {
  beforeEach(() => {
    vi.resetModules();
    withAuth.mockReset();
  });

  it("maps only server session fields needed by the control-plane DAL", async () => {
    withAuth.mockResolvedValue({
      user: { id: "user_01", email: "person@example.test", firstName: "Ada", lastName: "Lovelace" },
      accessToken: "signed-access-token",
      role: "untrusted-workos-role",
      organizationId: "untrusted-workos-organization",
      sessionId: "session_01",
    });
    const { requireSession } = await import("@/auth/session");

    const session = await requireSession();

    expect(session).toEqual({
      userId: "user_01",
      email: "person@example.test",
      displayName: "Ada Lovelace",
      accessToken: "signed-access-token",
    });
    expect(session).not.toHaveProperty("role");
    expect(session).not.toHaveProperty("organizationId");
  });

  it("rejects an incomplete SDK session", async () => {
    withAuth.mockResolvedValue({ user: { id: "user_01" } });
    const { requireSession } = await import("@/auth/session");

    await expect(requireSession()).rejects.toThrow("WorkOS returned an incomplete session");
  });

  it("requires only the keyless WorkOS variables and never exposes their values", async () => {
    const { validateAuthEnvironment } = await import("@/auth/config");
    const result = validateAuthEnvironment({
      WORKOS_CLIENT_ID: "client_01",
      WORKOS_COOKIE_PASSWORD: "x".repeat(32),
      NEXT_PUBLIC_WORKOS_REDIRECT_URI: "http://localhost:3000/auth/callback",
    });

    expect(result.redirectUri).toBe("http://localhost:3000/auth/callback");
    expect(JSON.stringify(result)).not.toContain("client_01");
    expect(JSON.stringify(result)).not.toContain("x".repeat(32));
  });
});
