import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { notFound, redirect, requireSession, revalidatePath } = vi.hoisted(() => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  redirect: vi.fn((location: string) => {
    throw new Error(`NEXT_REDIRECT:${location}`);
  }),
  requireSession: vi.fn(),
  revalidatePath: vi.fn(),
}));

vi.mock("next/navigation", () => ({ notFound, redirect }));
vi.mock("next/cache", () => ({ revalidatePath }));
vi.mock("@workos-inc/authkit-nextjs", () => ({ withAuth: vi.fn() }));
vi.mock("@/auth/session", () => ({ requireSession }));

import { requirePlatform } from "@/auth/platform";
import { hasPlatformCapability, PLATFORM_CAPABILITIES } from "@/auth/platform-permissions";
import { controlPlaneRequest } from "@/data/control-plane";
import {
  currentIdentitySchema,
  platformAuditEventSchema,
  platformIdentitySchema,
  tenantSummarySchema,
} from "@/data/schema";
import { grantStaffRoleAction, revokeStaffRoleAction } from "@/features/admin/actions";
import { LAST_PLATFORM_ADMIN_MESSAGE } from "@/features/admin/types";

const SESSION = { userId: "user-admin", email: "admin@example.test", displayName: "Admin", accessToken: "header.payload.signature" };
const ADMIN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const SUPPORT_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const REASON = "Support rota for Q4 onboarding";

const adminIdentity = {
  user_id: ADMIN_ID,
  email: "admin@example.test",
  role: "platform_admin",
  capabilities: ["platform_audit:read", "platform_staff:read", "platform_staff:write", "platform_tenant:read"],
};
const supportIdentity = { ...adminIdentity, user_id: SUPPORT_ID, role: "platform_support", capabilities: ["platform_tenant:read"] };

function jsonResponse(status: number, body: unknown) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("platform data boundary", () => {
  beforeEach(() => {
    process.env.WAVIA_CONTROL_PLANE_URL = "https://control-plane.test";
    requireSession.mockResolvedValue(SESSION);
  });

  afterEach(() => {
    delete process.env.WAVIA_CONTROL_PLANE_URL;
    vi.restoreAllMocks();
  });

  it("sends platform requests without tenant context", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, adminIdentity));

    await controlPlaneRequest("/v1/platform/me", {
      schema: platformIdentitySchema,
      session: SESSION,
      selectedTenantId: null,
      scope: "platform",
    });

    const headers = fetchSpy.mock.calls[0][1]?.headers as Headers;
    expect(headers.has("x-tenant-id")).toBe(false);
    expect(headers.has("x-actor-role")).toBe(false);
    expect(headers.get("authorization")).toBe(`Bearer ${SESSION.accessToken}`);
  });

  it("fails closed on platform capabilities", () => {
    expect(PLATFORM_CAPABILITIES).toEqual([
      "platform_tenant:read",
      "platform_staff:read",
      "platform_staff:write",
      "platform_audit:read",
      "platform_support_session:read",
      "platform_support_session:write",
      "platform_support_session:manage",
      "platform_operations:read",
    ]);
    expect(hasPlatformCapability(["platform_tenant:read"], "platform_tenant:read")).toBe(true);
    expect(hasPlatformCapability([], "platform_tenant:read")).toBe(false);
    expect(hasPlatformCapability(["*"], "platform_staff:write")).toBe(false);
    expect(hasPlatformCapability(["agent:write"], "platform_staff:write")).toBe(false);
  });

  it("parses the durable platform role on the identity and rejects unknown roles", () => {
    const base = { user_id: ADMIN_ID, email: null, is_active: true, is_platform_admin: false, memberships: [] };
    expect(currentIdentitySchema.parse(base)).toMatchObject({ platform_role: null, platform_capabilities: [] });
    expect(
      currentIdentitySchema.parse({ ...base, platform_role: "platform_support", platform_capabilities: ["platform_tenant:read"] }),
    ).toMatchObject({ platform_role: "platform_support" });
    expect(() => currentIdentitySchema.parse({ ...base, platform_role: "superadmin", platform_capabilities: [] })).toThrow();
    expect(() => platformIdentitySchema.parse({ ...adminIdentity, role: "tenant_admin" })).toThrow();
  });

  it("parses safe tenant summaries with partial role counts", () => {
    const summary = tenantSummarySchema.parse({
      tenant_id: "11111111-1111-4111-8111-111111111111",
      name: "Alpha workspace",
      created_at: "2026-01-01T00:00:00Z",
      members_by_role: { tenant_admin: 1, tenant_viewer: 3 },
      agent_count: null,
      entitlements: null,
      onboarding_completed_steps: ["business"],
    });
    expect(summary.members_by_role).toEqual({ tenant_admin: 1, tenant_viewer: 3 });
    expect(() =>
      tenantSummarySchema.parse({ ...summary, members_by_role: { platform_admin: 1 } }),
    ).toThrow();
    expect(
      platformAuditEventSchema.parse({
        event_id: "22222222-2222-4222-8222-222222222222",
        actor_user_id: null,
        action: "platform_staff.migrated",
        target_user_id: ADMIN_ID,
        target_tenant_id: null,
        previous_role: null,
        new_role: "platform_admin",
        reason: "Migrated from users.is_platform_admin",
        created_at: "2026-01-01T00:00:00Z",
      }).action,
    ).toBe("platform_staff.migrated");
  });
});

describe("requirePlatform", () => {
  beforeEach(() => {
    process.env.WAVIA_CONTROL_PLANE_URL = "https://control-plane.test";
    requireSession.mockResolvedValue(SESSION);
  });

  afterEach(() => {
    delete process.env.WAVIA_CONTROL_PLANE_URL;
    vi.restoreAllMocks();
  });

  it("hides the internal area from customers", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(403, { detail: "Platform staff role is required." }));
    await expect(requirePlatform()).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("denies staff a capability they do not hold without loading data", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, supportIdentity));
    await expect(requirePlatform("platform_staff:read")).rejects.toThrow("NEXT_REDIRECT:/admin?error=forbidden");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("returns the platform identity when the capability is held", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, adminIdentity));
    const context = await requirePlatform("platform_staff:write");
    expect(context.identity.role).toBe("platform_admin");
    expect(context.session).toBe(SESSION);
  });
});

describe("staff server actions", () => {
  beforeEach(() => {
    process.env.WAVIA_CONTROL_PLANE_URL = "https://control-plane.test";
    requireSession.mockResolvedValue(SESSION);
  });

  afterEach(() => {
    delete process.env.WAVIA_CONTROL_PLANE_URL;
    vi.restoreAllMocks();
  });

  it("rejects invalid input before contacting the control plane", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    expect(await grantStaffRoleAction({ email: "support@example.test", role: "platform_support", reason: "short" })).toMatchObject({
      ok: false,
      code: "invalid_request",
    });
    expect(
      await grantStaffRoleAction({ email: "support@example.test", role: "tenant_admin" as never, reason: REASON }),
    ).toMatchObject({ ok: false, code: "invalid_request" });
    expect(await revokeStaffRoleAction({ userId: "not-a-uuid", reason: REASON })).toMatchObject({ ok: false, code: "invalid_request" });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("re-checks the write capability on the server", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, supportIdentity));
    await expect(
      grantStaffRoleAction({ email: "support@example.test", role: "platform_support", reason: REASON }),
    ).rejects.toThrow("NEXT_REDIRECT:/admin?error=forbidden");
  });

  it("grants with a reason and maps control-plane failures", async () => {
    const granted = {
      user_id: SUPPORT_ID,
      email: "support@example.test",
      role: "platform_support",
      granted_by: ADMIN_ID,
      granted_at: "2026-01-01T00:00:00Z",
      reason: REASON,
    };
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(200, adminIdentity))
      .mockResolvedValueOnce(jsonResponse(200, granted))
      .mockResolvedValueOnce(jsonResponse(200, adminIdentity))
      .mockResolvedValueOnce(jsonResponse(404, { detail: "missing" }))
      .mockResolvedValueOnce(jsonResponse(200, adminIdentity))
      .mockResolvedValueOnce(jsonResponse(409, { detail: "last admin" }));

    const ok = await grantStaffRoleAction({ email: " Support@Example.test ", role: "platform_support", reason: `  ${REASON}  ` });
    expect(ok).toEqual({ ok: true, data: granted });
    const [url, init] = fetchSpy.mock.calls[1];
    expect(String(url)).toBe("https://control-plane.test/v1/platform/staff");
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(String(init?.body))).toEqual({ email: "support@example.test", role: "platform_support", reason: REASON });
    expect(revalidatePath).toHaveBeenCalledWith("/admin/staff");

    expect(await grantStaffRoleAction({ email: "ghost@example.test", role: "platform_support", reason: REASON })).toMatchObject({
      ok: false,
      code: "not_found",
    });
    expect(await grantStaffRoleAction({ email: "admin@example.test", role: "platform_support", reason: REASON })).toEqual({
      ok: false,
      code: "last_admin",
      message: LAST_PLATFORM_ADMIN_MESSAGE,
    });
  });

  it("revokes through the dedicated endpoint and maps the last-admin conflict", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(200, adminIdentity))
      .mockResolvedValueOnce(jsonResponse(204, null))
      .mockResolvedValueOnce(jsonResponse(200, adminIdentity))
      .mockResolvedValueOnce(jsonResponse(409, { detail: "last admin" }));

    expect(await revokeStaffRoleAction({ userId: SUPPORT_ID, reason: REASON })).toEqual({ ok: true, data: null });
    const [url, init] = fetchSpy.mock.calls[1];
    expect(String(url)).toBe(`https://control-plane.test/v1/platform/staff/${SUPPORT_ID}/revoke`);
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({ reason: REASON });

    expect(await revokeStaffRoleAction({ userId: ADMIN_ID, reason: REASON })).toMatchObject({ ok: false, code: "last_admin" });
  });
});
