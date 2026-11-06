// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@workos-inc/authkit-nextjs", () => ({ withAuth: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: () => "/agents" }));

import { WorkspaceNavigation } from "@/features/workspaces/workspace-navigation";
import { sealInvitationToken, unsealInvitationToken } from "@/auth/invitation";
import { hasWorkspaceCapability } from "@/auth/capabilities";
import {
  signWorkspaceSelection,
  verifyWorkspaceSelection,
  workspaceCookieOptions,
} from "@/auth/workspace";

const WORKSPACE_ID = "11111111-1111-4111-8111-111111111111";
const COOKIE_SECRET = "test-cookie-password-that-is-long-enough";

describe("workspace authorization", () => {
  it("signs only the workspace ID and rejects forged selections", () => {
    const signed = signWorkspaceSelection(WORKSPACE_ID, COOKIE_SECRET);

    expect(verifyWorkspaceSelection(signed, COOKIE_SECRET)).toBe(WORKSPACE_ID);
    expect(verifyWorkspaceSelection(`${signed}tampered`, COOKIE_SECRET)).toBeNull();
    expect(signed).not.toContain("tenant_admin");
  });

  it("uses secure HTTP-only finite cookie options", () => {
    expect(workspaceCookieOptions(true)).toMatchObject({
      httpOnly: true,
      sameSite: "lax",
      secure: true,
      path: "/",
    });
    expect(workspaceCookieOptions(true).maxAge).toBeGreaterThan(0);
  });

  it("keeps invitation handoff in a tamper-evident short-lived cookie", () => {
    const token = "invitation_token_with_enough_entropy_123";
    const sealed = sealInvitationToken(token, COOKIE_SECRET);

    expect(unsealInvitationToken(sealed, COOKIE_SECRET)).toBe(token);
    expect(unsealInvitationToken(`${sealed}x`, COOKIE_SECRET)).toBeNull();
    expect(sealed).not.toContain(token);
  });

  it("uses backend capabilities for presentation and fails closed", () => {
    expect(hasWorkspaceCapability(["member:write"], "member:write")).toBe(true);
    expect(hasWorkspaceCapability([], "member:write")).toBe(false);
    expect(hasWorkspaceCapability(["future:unknown"], "agent:read")).toBe(false);
  });

  it("renders task navigation from backend-provided capabilities", () => {
    const { rerender } = render(
      <WorkspaceNavigation capabilities={["agent:read", "session:read"]} role="tenant_viewer" />,
    );
    expect(screen.getByRole("link", { name: "Build" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("link", { name: "Connect" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();

    rerender(
      <WorkspaceNavigation capabilities={["agent:read", "telephony:read", "member:write"]} role="tenant_admin" />,
    );
    expect(screen.getByRole("link", { name: "Connect" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings" })).toBeInTheDocument();
  });

  it("does not trust forged administrator role text without capabilities", () => {
    const { container } = render(<WorkspaceNavigation capabilities={[]} role="tenant_admin" />);
    const navigation = within(container);

    expect(navigation.queryByRole("link", { name: "Build" })).not.toBeInTheDocument();
    expect(navigation.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
  });

  it("shows only the lean developer navigation bundle", () => {
    const { container } = render(
      <WorkspaceNavigation
        capabilities={[
          "agent:read",
          "session:mint",
          "session:read",
          "usage:read",
          "telephony:read",
          "api_key:read",
          "provider_credential:read",
        ]}
        role="tenant_developer"
      />,
    );
    const navigation = within(container);

    expect(navigation.getByRole("link", { name: "Build" })).toBeInTheDocument();
    expect(navigation.getByRole("link", { name: "Test" })).toBeInTheDocument();
    expect(navigation.getByRole("link", { name: "Connect" })).toBeInTheDocument();
    expect(navigation.getByRole("link", { name: "API keys" })).toBeInTheDocument();
    expect(navigation.getByRole("link", { name: "Providers" })).toBeInTheDocument();
    expect(navigation.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
  });

  it("collapses the workspace sidebar without removing accessible route names", () => {
    const { container } = render(
      <WorkspaceNavigation capabilities={["agent:read"]} displayName="Offline User" role="tenant_admin" tenantName="Alpha workspace" />,
    );
    const sidebar = within(container);

    expect(sidebar.getByRole("link", { name: /^Wavia Studio$/ })).toBeVisible();
    const toggle = sidebar.getByRole("button", { name: "Collapse sidebar" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(sidebar.getByText("Alpha workspace")).toBeVisible();
    expect(sidebar.getByText("Offline User")).toBeVisible();

    fireEvent.click(toggle);

    expect(sidebar.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute("aria-expanded", "false");
    expect(container.querySelector("[data-collapsed='true']")).toBeInTheDocument();
    expect(sidebar.getByRole("link", { name: "Build" })).toBeInTheDocument();
  });

  it("lets editors open read-only channel readiness without exposing admin credential screens", () => {
    const { container } = render(
      <WorkspaceNavigation capabilities={["telephony:read"]} role="tenant_editor" />,
    );
    const navigation = within(container);

    expect(navigation.getByRole("link", { name: "Connect" })).toBeInTheDocument();
    expect(navigation.queryByRole("link", { name: "API Keys" })).not.toBeInTheDocument();
    expect(navigation.queryByRole("link", { name: "Providers" })).not.toBeInTheDocument();
  });
});
