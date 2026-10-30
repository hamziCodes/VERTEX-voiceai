// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@workos-inc/authkit-nextjs", () => ({ withAuth: vi.fn() }));

import { WorkspaceNavigation } from "@/features/workspaces/workspace-navigation";
import { sealInvitationToken, unsealInvitationToken } from "@/auth/invitation";
import {
  hasWorkspacePermission,
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

  it("mirrors the backend permission matrix for early UX checks", () => {
    expect(hasWorkspacePermission("tenant_admin", "member:write")).toBe(true);
    expect(hasWorkspacePermission("tenant_editor", "agent:write")).toBe(true);
    expect(hasWorkspacePermission("tenant_editor", "member:write")).toBe(false);
    expect(hasWorkspacePermission("tenant_viewer", "agent:write")).toBe(false);
    expect(hasWorkspacePermission("compliance_admin", "audit:read")).toBe(true);
  });

  it("renders task navigation from durable Wavia role permissions", () => {
    const { rerender } = render(<WorkspaceNavigation role="tenant_viewer" />);
    expect(screen.getByRole("link", { name: "Build" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Connect" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();

    rerender(<WorkspaceNavigation role="tenant_admin" />);
    expect(screen.getByRole("link", { name: "Connect" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings" })).toBeInTheDocument();
  });
});
