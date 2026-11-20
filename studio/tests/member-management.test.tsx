// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { controlPlaneRequest, cookieStore, redirect, requireSession, requireWorkspace, revalidatePath, setSelectedWorkspace } = vi.hoisted(() => ({
  controlPlaneRequest: vi.fn(),
  cookieStore: { delete: vi.fn(), get: vi.fn(), set: vi.fn() },
  redirect: vi.fn((location: string) => {
    throw new Error(`NEXT_REDIRECT:${location}`);
  }),
  requireSession: vi.fn(),
  requireWorkspace: vi.fn(),
  revalidatePath: vi.fn(),
  setSelectedWorkspace: vi.fn(),
}));

vi.mock("next/navigation", () => ({ redirect, usePathname: () => "/settings/members" }));
vi.mock("next/cache", () => ({ revalidatePath }));
vi.mock("next/headers", () => ({ cookies: vi.fn(async () => cookieStore) }));
vi.mock("@workos-inc/authkit-nextjs", () => ({ getSignInUrl: vi.fn(), signOut: vi.fn(), withAuth: vi.fn() }));
vi.mock("@/auth/session", () => ({ requireSession }));
vi.mock("@/auth/config", () => ({ workspaceCookieSecret: () => `test-${"x".repeat(32)}` }));
vi.mock("@/auth/workspace", async () => {
  const permissions = await import("@/auth/workspace-permissions");
  return {
    hasWorkspaceCapability: permissions.hasWorkspaceCapability,
    listCurrentWorkspaces: vi.fn(),
    requireWorkspace,
    setSelectedWorkspace,
  };
});
vi.mock("@/data/control-plane", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/data/control-plane")>()),
  controlPlaneRequest,
}));

import SettingsPage from "@/app/(studio)/settings/page";
import MembersPage from "@/app/(studio)/settings/members/page";
import { sealInvitationToken } from "@/auth/invitation";
import { ControlPlaneError } from "@/data/control-plane";
import type { WorkspaceMemberDto } from "@/data/schema";
import { changeMemberRoleAction, inviteMemberAction, removeMemberAction } from "@/features/members/actions";
import { MemberManager, type MemberManagerProps } from "@/features/members/member-manager";
import { LAUNCH_ROLES } from "@/features/members/types";
import { acceptPendingInvitationAction } from "@/features/workspaces/actions";
import { WorkspaceNavigation } from "@/features/workspaces/workspace-navigation";

const TENANT = "11111111-1111-4111-8111-111111111111";
const ADMIN = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const EDITOR = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const VIEWER = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const INVITATION_TOKEN = "offline_invitation_token_value_0001";

const member = (userId: string, role: WorkspaceMemberDto["role"]): WorkspaceMemberDto => ({
  user_id: userId,
  tenant_id: TENANT,
  tenant_name: "Alpha workspace",
  role,
  created_at: "2026-11-01T00:00:00Z",
});

const members = [member(VIEWER, "tenant_viewer"), member(EDITOR, "tenant_editor"), member(ADMIN, "tenant_admin")];

function renderManager(overrides: Partial<MemberManagerProps> = {}) {
  const props: MemberManagerProps = {
    canManage: true,
    currentUserId: ADMIN,
    members,
    onChangeRole: vi.fn(async ({ userId, role }) => ({ ok: true as const, data: member(userId, role) })),
    onInvite: vi.fn(async ({ email, role }) => ({
      ok: true as const,
      data: { email, role, expiresAt: "2026-11-15T00:00:00Z", invitationPath: `/sign-in?invitation=${INVITATION_TOKEN}` },
    })),
    onRemove: vi.fn(async () => ({ ok: true as const, data: null })),
    workspaceName: "Alpha workspace",
    ...overrides,
  };
  return { props, ...render(<MemberManager {...props} />) };
}

const workspaceContext = (capabilities: string[], role = "tenant_admin") => ({
  session: { accessToken: "offline-access-token", displayName: "Offline User" },
  identity: { user_id: ADMIN, memberships: [] },
  membership: { user_id: ADMIN, tenant_id: TENANT, tenant_name: "Alpha workspace", role, capabilities, created_at: "2026-01-01T00:00:00Z" },
});

beforeEach(() => {
  controlPlaneRequest.mockReset();
  requireWorkspace.mockReset();
  revalidatePath.mockReset();
  redirect.mockClear();
  cookieStore.delete.mockReset();
  cookieStore.get.mockReset();
  setSelectedWorkspace.mockReset();
  requireSession.mockResolvedValue({ accessToken: "offline-access-token", displayName: "Offline User" });
});

afterEach(cleanup);

describe("member manager presentation", () => {
  it("shows editors a read-only member list without mutation controls", () => {
    renderManager({ canManage: false, currentUserId: EDITOR });

    const list = screen.getByRole("list", { name: "Workspace members" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(within(list).getAllByRole("listitem")[0]).toHaveTextContent("Administrator");
    expect(screen.getByText("Your role can view members but cannot invite, change roles, or remove members.")).toBeVisible();
    expect(screen.queryByRole("form", { name: "Invite a member" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove/ })).not.toBeInTheDocument();
    expect(screen.getByRole("listitem", { name: /^You/ })).toHaveTextContent("Editor");
  });

  it("offers exactly the five launch roles and defaults to least privilege", () => {
    renderManager();

    const roleGroup = screen.getByRole("group", { name: "Role" });
    const radios = within(roleGroup).getAllByRole("radio");
    expect(radios.map((radio) => (radio as HTMLInputElement).value)).toEqual([...LAUNCH_ROLES]);
    expect(LAUNCH_ROLES).toEqual(["tenant_admin", "tenant_editor", "tenant_developer", "tenant_viewer", "compliance_admin"]);
    expect(within(roleGroup).getByRole("radio", { name: /Read-only operator/ })).toBeChecked();
  });

  it("warns explicitly before inviting a tenant administrator", () => {
    renderManager();

    expect(screen.queryByText(/Administrators can invite and remove members/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /^Administrator/ }));
    expect(screen.getByRole("note")).toHaveTextContent("Administrators can invite and remove members");
  });

  it("reveals the invitation link once without browser storage and clears it on dismissal", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const { props } = renderManager();

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "new.person@example.test" } });
    fireEvent.click(screen.getByRole("radio", { name: /^Developer/ }));
    fireEvent.click(screen.getByRole("button", { name: "Create invitation" }));

    await waitFor(() => expect(props.onInvite).toHaveBeenCalledWith({ email: "new.person@example.test", role: "tenant_developer" }));
    const reveal = await screen.findByRole("region", { name: "Invitation link for new.person@example.test" });
    expect(within(reveal).getByLabelText("Invitation link")).toHaveValue(`${window.location.origin}/sign-in?invitation=${INVITATION_TOKEN}`);
    expect(within(reveal).getByText(/shown once/)).toBeVisible();
    expect(screen.getByRole("list", { name: "Workspace members" })).not.toHaveTextContent(INVITATION_TOKEN);

    fireEvent.click(within(reveal).getByRole("button", { name: "Done" }));
    expect(screen.queryByRole("region", { name: /Invitation link/ })).not.toBeInTheDocument();
    expect(document.body.innerHTML).not.toContain(INVITATION_TOKEN);
    expect(setItem).not.toHaveBeenCalled();
  });

  it("shows an invitation failure without revealing anything", async () => {
    renderManager({ onInvite: vi.fn(async () => ({ ok: false as const, code: "forbidden" as const, message: "Only workspace administrators can manage members." })) });

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "new.person@example.test" } });
    fireEvent.click(screen.getByRole("button", { name: "Create invitation" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Only workspace administrators can manage members.");
    expect(screen.queryByRole("region", { name: /Invitation link/ })).not.toBeInTheDocument();
  });

  it("updates a member role through the narrow action and warns when promoting to administrator", async () => {
    const { props } = renderManager();
    const editorRow = screen.getByRole("listitem", { name: /bbbbbbbb/ });

    fireEvent.change(within(editorRow).getByRole("combobox", { name: /Role for/ }), { target: { value: "tenant_admin" } });
    expect(within(editorRow).getByRole("note")).toHaveTextContent("Administrators can invite and remove members");
    fireEvent.change(within(editorRow).getByRole("combobox", { name: /Role for/ }), { target: { value: "tenant_viewer" } });
    fireEvent.click(within(editorRow).getByRole("button", { name: /Update role/ }));

    await waitFor(() => expect(props.onChangeRole).toHaveBeenCalledWith({ userId: EDITOR, role: "tenant_viewer" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Role updated to Read-only operator.");
  });

  it("requires confirmation before removing a member", async () => {
    const { props } = renderManager();
    const viewerRow = screen.getByRole("listitem", { name: /cccccccc/ });

    fireEvent.click(within(viewerRow).getByRole("button", { name: /Remove/ }));
    const dialog = screen.getByRole("dialog", { name: "Remove member" });
    expect(dialog).toHaveTextContent("They lose access to Alpha workspace immediately.");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(props.onRemove).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(within(viewerRow).getByRole("button", { name: /Remove/ }));
    fireEvent.click(within(screen.getByRole("dialog", { name: "Remove member" })).getByRole("button", { name: "Remove member" }));
    await waitFor(() => expect(props.onRemove).toHaveBeenCalledWith({ userId: VIEWER }));
    expect(await screen.findByRole("status")).toHaveTextContent("Member removed.");
  });

  it("protects the last administrator in the interface", () => {
    renderManager();
    const adminRow = screen.getByRole("listitem", { name: /^You/ });

    expect(within(adminRow).getByRole("combobox", { name: /Role for/ })).toBeDisabled();
    expect(within(adminRow).getByRole("button", { name: /Remove/ })).toBeDisabled();
    expect(within(adminRow).getByText("Last administrator. Promote another member before changing or removing this role.")).toBeVisible();
  });

  it("surfaces a server last-administrator conflict instead of claiming success", async () => {
    const twoAdmins = [member(ADMIN, "tenant_admin"), member(EDITOR, "tenant_admin")];
    renderManager({
      members: twoAdmins,
      onChangeRole: vi.fn(async () => ({ ok: false as const, code: "last_admin" as const, message: "A workspace must keep at least one administrator. Promote another member first." })),
    });
    const row = screen.getByRole("listitem", { name: /bbbbbbbb/ });

    fireEvent.change(within(row).getByRole("combobox", { name: /Role for/ }), { target: { value: "tenant_editor" } });
    fireEvent.click(within(row).getByRole("button", { name: /Update role/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("A workspace must keep at least one administrator.");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("member server actions", () => {
  it("rejects roles outside the five launch roles before contacting the control plane", async () => {
    requireWorkspace.mockResolvedValue(workspaceContext(["member:read", "member:write"]));

    const result = await inviteMemberAction({ email: "x@example.test", role: "tenant_owner" } as never);

    expect(result).toEqual({ ok: false, code: "invalid_request", message: expect.any(String) });
    expect(controlPlaneRequest).not.toHaveBeenCalled();
  });

  it("repeats member:write authorization and returns the token only inside the one-time link", async () => {
    const log = vi.spyOn(console, "log");
    const info = vi.spyOn(console, "info");
    const error = vi.spyOn(console, "error");
    requireWorkspace.mockResolvedValue(workspaceContext(["member:read", "member:write"]));
    controlPlaneRequest.mockResolvedValue({
      invitation_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      tenant_id: TENANT,
      email: "new.person@example.test",
      role: "tenant_editor",
      invited_by: ADMIN,
      expires_at: "2026-11-15T00:00:00Z",
      accepted_at: null,
      accepted_by: null,
      created_at: "2026-11-12T00:00:00Z",
      token: INVITATION_TOKEN,
    });

    const result = await inviteMemberAction({ email: " New.Person@Example.test ", role: "tenant_editor" });

    expect(requireWorkspace).toHaveBeenCalledWith("member:write");
    expect(controlPlaneRequest).toHaveBeenCalledWith(`/v1/organizations/${TENANT}/invitations`, expect.objectContaining({
      method: "POST",
      json: { email: "new.person@example.test", role: "tenant_editor" },
      selectedTenantId: TENANT,
    }));
    expect(result).toEqual({
      ok: true,
      data: { email: "new.person@example.test", role: "tenant_editor", expiresAt: "2026-11-15T00:00:00Z", invitationPath: `/sign-in?invitation=${INVITATION_TOKEN}` },
    });
    expect(JSON.stringify(result).match(new RegExp(INVITATION_TOKEN, "g"))).toHaveLength(1);
    for (const spy of [log, info, error]) {
      expect(JSON.stringify(spy.mock.calls)).not.toContain(INVITATION_TOKEN);
    }
  });

  it("maps a control-plane last-administrator conflict on role change", async () => {
    requireWorkspace.mockResolvedValue(workspaceContext(["member:read", "member:write"]));
    controlPlaneRequest.mockRejectedValue(new ControlPlaneError({ code: "conflict", message: "This record changed. Refresh and try again." }, 409));

    const result = await changeMemberRoleAction({ userId: ADMIN, role: "tenant_viewer" });

    expect(requireWorkspace).toHaveBeenCalledWith("member:write");
    expect(controlPlaneRequest).toHaveBeenCalledWith(`/v1/organizations/${TENANT}/members/${ADMIN}`, expect.objectContaining({ method: "PATCH", json: { role: "tenant_viewer" } }));
    expect(result).toEqual({ ok: false, code: "last_admin", message: "A workspace must keep at least one administrator. Promote another member first." });
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it("maps a last-administrator conflict on removal and rejects malformed member ids", async () => {
    requireWorkspace.mockResolvedValue(workspaceContext(["member:read", "member:write"]));
    controlPlaneRequest.mockRejectedValue(new ControlPlaneError({ code: "conflict", message: "This record changed. Refresh and try again." }, 409));

    expect(await removeMemberAction({ userId: "../../agents" })).toEqual({ ok: false, code: "invalid_request", message: expect.any(String) });
    expect(controlPlaneRequest).not.toHaveBeenCalled();

    expect(await removeMemberAction({ userId: ADMIN })).toEqual({ ok: false, code: "last_admin", message: expect.stringContaining("at least one administrator") });
    expect(controlPlaneRequest).toHaveBeenCalledWith(`/v1/organizations/${TENANT}/members/${ADMIN}`, expect.objectContaining({ method: "DELETE" }));
  });

  it("revalidates the member list after a successful removal", async () => {
    requireWorkspace.mockResolvedValue(workspaceContext(["member:read", "member:write"]));
    controlPlaneRequest.mockResolvedValue(null);

    expect(await removeMemberAction({ userId: VIEWER })).toEqual({ ok: true, data: null });
    expect(revalidatePath).toHaveBeenCalledWith("/settings/members");
  });
});

describe("invitation acceptance failures", () => {
  function pendingInvitation() {
    cookieStore.get.mockReturnValue({ value: sealInvitationToken(INVITATION_TOKEN, `test-${"x".repeat(32)}`) });
  }

  it("explains an expired invitation and discards the pending cookie", async () => {
    pendingInvitation();
    controlPlaneRequest.mockRejectedValue(new ControlPlaneError({ code: "upstream_unavailable", message: "The service could not complete the request." }, 410));

    await expect(acceptPendingInvitationAction()).rejects.toThrow("NEXT_REDIRECT:/workspaces?error=invitation-expired");
    expect(cookieStore.delete).toHaveBeenCalledWith("wavia-pending-invitation");
    expect(setSelectedWorkspace).not.toHaveBeenCalled();
  });

  it("explains a replayed invitation and discards the pending cookie", async () => {
    pendingInvitation();
    controlPlaneRequest.mockRejectedValue(new ControlPlaneError({ code: "conflict", message: "This record changed. Refresh and try again." }, 409));

    await expect(acceptPendingInvitationAction()).rejects.toThrow("NEXT_REDIRECT:/workspaces?error=invitation-used");
    expect(cookieStore.delete).toHaveBeenCalledWith("wavia-pending-invitation");
  });

  it("explains an invitation addressed to a different email", async () => {
    pendingInvitation();
    controlPlaneRequest.mockRejectedValue(new ControlPlaneError({ code: "forbidden", message: "You do not have permission for this action." }, 403));

    await expect(acceptPendingInvitationAction()).rejects.toThrow("NEXT_REDIRECT:/workspaces?error=invitation-mismatch");
  });

  it("accepts the FastAPI membership shape, which carries no capabilities", async () => {
    pendingInvitation();
    controlPlaneRequest.mockImplementation(async (_path: string, options: { schema: { parse(value: unknown): unknown } }) =>
      options.schema.parse(member(ADMIN, "tenant_editor")));

    await expect(acceptPendingInvitationAction()).rejects.toThrow("NEXT_REDIRECT:/dashboard");
    expect(setSelectedWorkspace).toHaveBeenCalledWith(TENANT);
    expect(cookieStore.delete).toHaveBeenCalledWith("wavia-pending-invitation");
  });

  it("keeps the pending invitation when the service is temporarily unavailable", async () => {
    pendingInvitation();
    const unavailable = new ControlPlaneError({ code: "upstream_unavailable", message: "The service is temporarily unavailable." }, 503);
    controlPlaneRequest.mockRejectedValue(unavailable);

    await expect(acceptPendingInvitationAction()).rejects.toBe(unavailable);
    expect(cookieStore.delete).not.toHaveBeenCalled();
  });
});

describe("settings routes and navigation", () => {
  it("lists only capability-eligible settings destinations", async () => {
    requireWorkspace.mockResolvedValue(workspaceContext(["member:read", "usage:read", "audit:read"], "tenant_editor"));

    render(await SettingsPage());

    expect(screen.getByRole("link", { name: /Members/ })).toHaveAttribute("href", "/settings/members");
    expect(screen.getByRole("link", { name: /Usage/ })).toHaveAttribute("href", "/settings/usage");
    expect(screen.getByRole("link", { name: /Audit/ })).toHaveAttribute("href", "/settings/audit");
    expect(screen.queryByRole("link", { name: /Provider/ })).not.toBeInTheDocument();
  });

  it("renders an honest state when no settings destination is permitted", async () => {
    requireWorkspace.mockResolvedValue(workspaceContext([], "tenant_viewer"));

    render(await SettingsPage());

    expect(screen.getByRole("heading", { name: "No workspace settings for your role" })).toBeVisible();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("requires member:read for the members route and member:write for controls", async () => {
    requireWorkspace.mockResolvedValue(workspaceContext(["member:read"], "tenant_editor"));
    controlPlaneRequest.mockResolvedValue([member(ADMIN, "tenant_admin")]);

    render(await MembersPage());

    expect(requireWorkspace).toHaveBeenCalledWith("member:read");
    expect(controlPlaneRequest).toHaveBeenCalledWith(`/v1/organizations/${TENANT}/members`, expect.objectContaining({ selectedTenantId: TENANT }));
    expect(screen.getByRole("heading", { name: "Members" })).toBeVisible();
    expect(screen.queryByRole("form", { name: "Invite a member" })).not.toBeInTheDocument();
  });

  it("shows Settings to member readers, marks Members active and hides it from developers", () => {
    const { rerender } = render(<WorkspaceNavigation capabilities={["member:read"]} role="tenant_editor" />);
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");

    rerender(<WorkspaceNavigation capabilities={["usage:read", "api_key:read", "provider_credential:read"]} role="tenant_developer" />);
    expect(screen.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
  });
});
