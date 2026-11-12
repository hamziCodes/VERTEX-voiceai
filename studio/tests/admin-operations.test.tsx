// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { controlPlaneRequest, notFound, redirect, requirePlatform } = vi.hoisted(() => ({
  controlPlaneRequest: vi.fn(),
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  redirect: vi.fn((location: string) => {
    throw new Error(`NEXT_REDIRECT:${location}`);
  }),
  requirePlatform: vi.fn(),
}));

vi.mock("next/navigation", () => ({ notFound, redirect, usePathname: () => "/admin/operations" }));
vi.mock("@workos-inc/authkit-nextjs", () => ({ withAuth: vi.fn() }));
vi.mock("@/auth/platform", async () => {
  const permissions = await import("@/auth/platform-permissions");
  return { hasPlatformCapability: permissions.hasPlatformCapability, requirePlatform };
});
vi.mock("@/data/control-plane", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/data/control-plane")>()),
  controlPlaneRequest,
}));

import OperationsPage from "@/app/(admin)/admin/operations/page";
import { AdminNavigation } from "@/features/admin/admin-navigation";

const snapshot = {
  checked_at: "2026-11-12T10:00:00Z",
  environment: "test",
  signals: [
    { key: "control_plane", label: "Control plane", status: "healthy", detail: "The control plane is serving requests.", metrics: {} },
    { key: "database", label: "Database", status: "not_configured", detail: "No PostgreSQL database is configured; in-memory repositories are in use.", metrics: {} },
    { key: "post_call_queue", label: "Post-call jobs", status: "attention", detail: "Some post-call jobs exhausted their retries and need review.", metrics: { queued: 2, running: 0, retry_wait: 1, succeeded: 10, dead_letter: 1 } },
    { key: "live_providers", label: "Live provider traffic", status: "disabled", detail: "Live provider traffic is disabled in this environment.", metrics: {} },
    { key: "provider_health", label: "Provider health", status: "not_measured", detail: "No live provider health probe runs from the control plane.", metrics: {} },
  ],
};

describe("platform operations", () => {
  beforeEach(() => {
    requirePlatform.mockResolvedValue({
      session: { userId: "user", email: "admin@example.test", displayName: "Ada", accessToken: "a.b.c" },
      identity: { user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", email: "admin@example.test", role: "platform_admin", capabilities: ["platform_operations:read", "platform_tenant:read"] },
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("lists Operations only with platform_operations:read", () => {
    render(<AdminNavigation capabilities={["platform_operations:read"]} role="platform_admin" />);
    expect(screen.getByRole("link", { name: "Operations" })).toHaveAttribute("aria-current", "page");
    cleanup();
    render(<AdminNavigation capabilities={["platform_tenant:read", "platform_support_session:read"]} role="platform_support" />);
    expect(screen.queryByRole("link", { name: "Operations" })).not.toBeInTheDocument();
  });

  it("shows every signal with a text status, metrics and an honest note", async () => {
    controlPlaneRequest.mockResolvedValue(snapshot);
    render(await OperationsPage());

    expect(requirePlatform).toHaveBeenCalledWith("platform_operations:read");
    expect(controlPlaneRequest.mock.calls[0][0]).toBe("/v1/platform/operations");
    expect(screen.getByRole("heading", { level: 1, name: "Operations" })).toBeInTheDocument();
    expect(screen.getByText("Checked 12 Nov 2026, 10:00 UTC · environment test")).toBeInTheDocument();
    expect(screen.getByText(/Live provider and carrier probes do not run/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("1 signal needs attention");

    const list = screen.getByRole("list", { name: "Platform signals" });
    const card = (name: string) => within(list).getByRole("listitem", { name });
    expect(within(card("Control plane")).getByText("Healthy")).toBeInTheDocument();
    expect(within(card("Database")).getByText("Not configured")).toBeInTheDocument();
    expect(within(card("Live provider traffic")).getByText("Disabled")).toBeInTheDocument();
    expect(within(card("Provider health")).getByText("Not measured")).toBeInTheDocument();
    const queue = card("Post-call jobs");
    expect(within(queue).getByText("Attention")).toBeInTheDocument();
    expect(within(queue).getByText("Dead letter")).toBeInTheDocument();
    expect(within(queue).getByText("Waiting to retry")).toBeInTheDocument();
    expect(within(queue).getByText("10")).toBeInTheDocument();
  });

  it("states when nothing needs attention", async () => {
    controlPlaneRequest.mockResolvedValue({ ...snapshot, signals: snapshot.signals.filter((item) => item.status !== "attention") });
    render(await OperationsPage());
    expect(screen.getByRole("status")).toHaveTextContent("No signal needs attention");
  });
});
