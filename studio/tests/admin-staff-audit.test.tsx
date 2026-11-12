// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

vi.mock("next/navigation", () => ({ notFound, redirect, usePathname: () => "/admin/staff" }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("@workos-inc/authkit-nextjs", () => ({ withAuth: vi.fn() }));
vi.mock("@/auth/platform", async () => {
  const permissions = await import("@/auth/platform-permissions");
  return { hasPlatformCapability: permissions.hasPlatformCapability, requirePlatform };
});
vi.mock("@/data/control-plane", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/data/control-plane")>()),
  controlPlaneRequest,
}));

import AuditPage from "@/app/(admin)/admin/audit/page";
import StaffPage from "@/app/(admin)/admin/staff/page";
import type { PlatformAuditEventDto, PlatformStaffMemberDto } from "@/data/schema";
import { StaffManager, type StaffManagerProps } from "@/features/admin/staff-manager";
import { LAST_PLATFORM_ADMIN_MESSAGE } from "@/features/admin/types";

const ADMIN = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const SUPPORT = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const TENANT = "11111111-1111-4111-8111-111111111111";
const REASON = "Support rota for Q4 onboarding";
const ADMIN_CAPABILITIES = ["platform_audit:read", "platform_staff:read", "platform_staff:write", "platform_tenant:read"];

const staffMember = (userId: string, role: PlatformStaffMemberDto["role"], email: string): PlatformStaffMemberDto => ({
  user_id: userId,
  email,
  role,
  granted_by: null,
  granted_at: "2026-01-02T09:30:00Z",
  reason: "Initial operator bootstrap",
});

function renderManager(overrides: Partial<StaffManagerProps> = {}) {
  const props: StaffManagerProps = {
    canManage: true,
    currentUserId: ADMIN,
    staff: [staffMember(ADMIN, "platform_admin", "admin@example.test"), staffMember(SUPPORT, "platform_support", "support@example.test")],
    onGrant: vi.fn(),
    onRevoke: vi.fn(),
    ...overrides,
  };
  render(<StaffManager {...props} />);
  return props;
}

describe("platform staff management", () => {
  beforeEach(() => {
    requirePlatform.mockResolvedValue({
      session: { userId: "user-admin", email: "admin@example.test", displayName: "Ada", accessToken: "a.b.c" },
      identity: { user_id: ADMIN, email: "admin@example.test", role: "platform_admin", capabilities: ADMIN_CAPABILITIES },
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("loads staff behind platform_staff:read and lists roles as text", async () => {
    controlPlaneRequest.mockResolvedValue([staffMember(ADMIN, "platform_admin", "admin@example.test")]);
    render(await StaffPage());
    expect(requirePlatform).toHaveBeenCalledWith("platform_staff:read");
    expect(controlPlaneRequest.mock.calls[0][0]).toBe("/v1/platform/staff");
    expect(screen.getByRole("heading", { level: 1, name: "Staff" })).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Platform staff" });
    const row = within(table).getByRole("row", { name: /admin@example\.test/ });
    expect(within(row).getByText("You")).toBeInTheDocument();
    expect(within(row).getByText("Platform administrator")).toBeInTheDocument();
    expect(within(row).getByText("2 Jan 2026")).toBeInTheDocument();
  });

  it("protects the last platform administrator in the interface", () => {
    renderManager({ staff: [staffMember(ADMIN, "platform_admin", "admin@example.test")] });
    const row = screen.getByRole("row", { name: /admin@example\.test/ });
    expect(within(row).getByRole("button", { name: /Revoke/ })).toBeDisabled();
    expect(within(row).getByRole("button", { name: /Change role/ })).toBeDisabled();
    expect(within(row).getByText("Last platform administrator.")).toBeInTheDocument();
  });

  it("hides write controls without platform_staff:write", () => {
    renderManager({ canManage: false });
    expect(screen.queryByRole("button", { name: "Grant a role" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Revoke/ })).not.toBeInTheDocument();
    expect(screen.getByText(/can view staff but not change roles/)).toBeInTheDocument();
  });

  it("grants a role with a required reason and keeps the dialog open on failure", async () => {
    const granted = staffMember("cccccccc-cccc-4ccc-8ccc-cccccccccccc", "platform_support", "new@example.test");
    const onGrant = vi.fn()
      .mockResolvedValueOnce({ ok: false, code: "not_found", message: "No active Wavia user matches." })
      .mockResolvedValueOnce({ ok: true, data: granted });
    renderManager({ onGrant });

    fireEvent.click(screen.getByRole("button", { name: "Grant a role" }));
    const dialog = screen.getByRole("dialog", { name: "Grant a platform role" });
    expect(within(dialog).getByLabelText("Email address")).toHaveFocus();
    fireEvent.change(within(dialog).getByLabelText("Email address"), { target: { value: "new@example.test" } });
    fireEvent.change(within(dialog).getByLabelText("Platform role"), { target: { value: "platform_support" } });
    expect(within(dialog).getByRole("button", { name: "Grant role" })).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText("Reason"), { target: { value: REASON } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Grant role" }));

    await waitFor(() => expect(within(dialog).getByRole("alert")).toHaveTextContent("No active Wavia user matches."));
    expect(onGrant).toHaveBeenCalledWith({ email: "new@example.test", role: "platform_support", reason: REASON });

    fireEvent.click(within(dialog).getByRole("button", { name: "Grant role" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent("new@example.test now has Platform support.");
    expect(screen.getByRole("row", { name: /new@example\.test/ })).toBeInTheDocument();
  });

  it("changes a role through the same reasoned grant", async () => {
    const changed = { ...staffMember(SUPPORT, "platform_admin", "support@example.test"), granted_by: ADMIN };
    const onGrant = vi.fn().mockResolvedValue({ ok: true, data: changed });
    renderManager({ onGrant });

    const row = screen.getByRole("row", { name: /support@example\.test/ });
    fireEvent.click(within(row).getByRole("button", { name: /Change role/ }));
    const dialog = screen.getByRole("dialog", { name: "Change platform role" });
    fireEvent.change(within(dialog).getByLabelText("Platform role"), { target: { value: "platform_admin" } });
    fireEvent.change(within(dialog).getByLabelText("Reason"), { target: { value: "Promoted to administration" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Change role" }));

    await waitFor(() => expect(onGrant).toHaveBeenCalledWith({ email: "support@example.test", role: "platform_admin", reason: "Promoted to administration" }));
    await waitFor(() => expect(within(screen.getByRole("row", { name: /support@example\.test/ })).getByText("Platform administrator")).toBeInTheDocument());
  });

  it("revokes only after a reasoned confirmation and surfaces the last-admin conflict", async () => {
    const onRevoke = vi.fn()
      .mockResolvedValueOnce({ ok: false, code: "last_admin", message: LAST_PLATFORM_ADMIN_MESSAGE })
      .mockResolvedValueOnce({ ok: true, data: null });
    renderManager({ onRevoke });

    const row = screen.getByRole("row", { name: /support@example\.test/ });
    fireEvent.click(within(row).getByRole("button", { name: /Revoke/ }));
    const dialog = screen.getByRole("dialog", { name: "Revoke platform role" });
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    fireEvent.click(within(dialog).getByRole("button", { name: "Revoke role" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Give a reason of at least 8 characters.");
    expect(onRevoke).not.toHaveBeenCalled();

    fireEvent.change(within(dialog).getByLabelText("Reason"), { target: { value: "Left the support rota" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Revoke role" }));
    await waitFor(() => expect(within(dialog).getByRole("alert")).toHaveTextContent(LAST_PLATFORM_ADMIN_MESSAGE));
    expect(onRevoke).toHaveBeenCalledWith({ userId: SUPPORT, reason: "Left the support rota" });

    fireEvent.click(within(dialog).getByRole("button", { name: "Revoke role" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.queryByRole("row", { name: /support@example\.test/ })).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Revoked the platform role for support@example.test.");
  });
});

describe("platform audit", () => {
  beforeEach(() => {
    requirePlatform.mockResolvedValue({
      session: { userId: "user-admin", email: "admin@example.test", displayName: "Ada", accessToken: "a.b.c" },
      identity: { user_id: ADMIN, email: "admin@example.test", role: "platform_admin", capabilities: ADMIN_CAPABILITIES },
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const event = (overrides: Partial<PlatformAuditEventDto>): PlatformAuditEventDto => ({
    event_id: "22222222-2222-4222-8222-222222222222",
    actor_user_id: ADMIN,
    action: "platform_tenant.viewed",
    target_user_id: null,
    target_tenant_id: TENANT,
    previous_role: null,
    new_role: null,
    reason: null,
    created_at: "2026-11-04T09:00:00Z",
    support_session_id: null,
    scope: null,
    ...overrides,
  });

  it("lists recent platform events with fixed UTC times and readable actions", async () => {
    controlPlaneRequest.mockResolvedValue([
      event({}),
      event({ event_id: "33333333-3333-4333-8333-333333333333", action: "platform_staff.role_changed", target_tenant_id: null, target_user_id: SUPPORT, previous_role: "platform_support", new_role: "platform_admin", reason: "Promoted to administration" }),
      event({ event_id: "44444444-4444-4444-8444-444444444444", actor_user_id: null, action: "platform_staff.migrated", target_tenant_id: null, target_user_id: ADMIN, new_role: "platform_admin" }),
      event({ event_id: "55555555-5555-4555-8555-555555555555", action: "platform_future.action", target_tenant_id: null }),
    ]);
    render(await AuditPage());

    expect(requirePlatform).toHaveBeenCalledWith("platform_audit:read");
    expect(controlPlaneRequest.mock.calls[0][0]).toBe("/v1/platform/audit?limit=50");
    const table = screen.getByRole("table", { name: "Platform audit events" });
    expect(within(table).getAllByText("4 Nov 2026, 09:00 UTC")).toHaveLength(4);
    expect(within(table).getByText("Tenant summary viewed")).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: /11111111/ })).toHaveAttribute("href", `/admin/tenants/${TENANT}`);
    expect(within(table).getByText("Platform support → Platform administrator")).toBeInTheDocument();
    expect(within(table).getByText("Promoted to administration")).toBeInTheDocument();
    expect(within(table).getByText("System migration")).toBeInTheDocument();
    expect(within(table).getByText("platform_future.action")).toBeInTheDocument();
  });

  it("shows an honest empty state", async () => {
    controlPlaneRequest.mockResolvedValue([]);
    render(await AuditPage());
    expect(screen.getByRole("heading", { name: "No platform events yet" })).toBeInTheDocument();
  });
});
