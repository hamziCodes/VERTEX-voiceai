// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { listCurrentWorkspaces, requireSession } = vi.hoisted(() => ({
  listCurrentWorkspaces: vi.fn(),
  requireSession: vi.fn(),
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: vi.fn(() => undefined) })),
}));
vi.mock("@/auth/session", () => ({ requireSession }));
vi.mock("@/auth/workspace", () => ({ listCurrentWorkspaces }));
vi.mock("@/features/workspaces/actions", () => ({
  acceptPendingInvitationAction: vi.fn(),
  createWorkspaceAction: vi.fn(),
  selectWorkspaceAction: vi.fn(),
  signOutAction: vi.fn(),
  startSignInAction: vi.fn(),
  startSignUpAction: vi.fn(),
}));

import StudioError from "@/app/error";
import NotFoundPage from "@/app/not-found";
import StudioHomePage from "@/app/page";
import SignInPage from "@/app/sign-in/page";
import SignUpPage from "@/app/sign-up/page";
import WorkspacesPage from "@/app/workspaces/page";
import { FormField } from "@/components/studio/form-field";
import { PageHeader } from "@/components/studio/page-header";
import { StatePanel } from "@/components/studio/state-panel";
import { StatusBadge } from "@/components/studio/status-badge";

const membership = (tenantId: string, name: string, role: "tenant_admin" | "tenant_viewer") => ({
  tenant_id: tenantId,
  tenant_name: name,
  role,
  capabilities: role === "tenant_admin" ? ["member:read", "member:write"] : ["agent:read"],
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("shared Studio composition primitives", () => {
  it("connects page headings, statuses, form guidance and state semantics", () => {
    render(
      <>
        <PageHeader eyebrow="Workspace" title="Choose where to work" summary="Your access follows each membership." />
        <StatusBadge tone="success">Active</StatusBadge>
        <FormField error="A name is required." hint="Visible to your team." label="Agent name" name="agentName">
          <input id="agentName" name="agentName" />
        </FormField>
        <StatePanel description="Try again in a moment." title="Could not load" tone="error" />
        <StatePanel description="Checking your memberships." title="Loading workspaces" tone="loading" />
      </>,
    );

    expect(screen.getByRole("heading", { name: "Choose where to work", level: 1 })).toBeVisible();
    expect(screen.getByText("Active")).toHaveClass("status-badge--success");
    expect(screen.getByLabelText("Agent name")).toHaveAccessibleDescription("Visible to your team. A name is required.");
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load");
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
  });
});

describe("public Studio entry", () => {
  it("offers one clear route into secure sign-in without marketing filler", () => {
    render(<StudioHomePage />);

    expect(screen.getByRole("heading", { name: "Build and operate your voice agents" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Sign in to Studio" })).toHaveAttribute("href", "/sign-in");
    expect(document.body).not.toHaveTextContent(/revolutionize|unleash|elevate/i);
  });

  it("preserves invitation handoff and requires an explicit sign-in action", async () => {
    render(await SignInPage({ searchParams: Promise.resolve({ invitation: "invite-safe-test-value" }) }));

    expect(screen.getByRole("heading", { name: "Sign in to Wavia Studio" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Continue securely" })).toBeVisible();
    expect(document.querySelector<HTMLInputElement>('input[name="invitation"]')?.value).toBe("invite-safe-test-value");
    expect(screen.getByRole("button", { name: "Create an account" })).toBeVisible();
  });

  it("offers hosted sign-up and keeps the invitation through it", async () => {
    render(await SignUpPage({ searchParams: Promise.resolve({ invitation: "invite-safe-test-value" }) }));

    expect(screen.getByRole("heading", { name: "Start building with Wavia" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Create an account" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/sign-in?invitation=invite-safe-test-value");
    expect(document.querySelector<HTMLInputElement>('input[name="invitation"]')?.value).toBe("invite-safe-test-value");
  });
});

describe("workspace selection", () => {
  it("renders multiple durable memberships with readable roles", async () => {
    requireSession.mockResolvedValue({ displayName: "Hamzi" });
    listCurrentWorkspaces.mockResolvedValue({
      platform_capabilities: [],
      memberships: [
        membership("11111111-1111-4111-8111-111111111111", "Alpha workspace", "tenant_admin"),
        membership("22222222-2222-4222-8222-222222222222", "Beta workspace", "tenant_viewer"),
      ],
    });

    render(await WorkspacesPage({ searchParams: Promise.resolve({}) }));

    const list = screen.getByRole("list", { name: "Available workspaces" });
    expect(within(list).getByRole("button", { name: /Alpha workspace/ })).toBeVisible();
    expect(within(list).getByText("Administrator")).toBeVisible();
    expect(within(list).getByText("Read-only operator")).toBeVisible();
  });

  it("shows honest empty, invitation and invalid-selection states", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValueOnce({ get: vi.fn(() => ({ value: "sealed" })) } as never);
    requireSession.mockResolvedValue({ displayName: "Hamzi" });
    listCurrentWorkspaces.mockResolvedValue({ platform_capabilities: [], memberships: [] });

    render(await WorkspacesPage({ searchParams: Promise.resolve({ error: "invalid-workspace" }) }));

    expect(screen.getByRole("alert")).toHaveTextContent("That workspace is not available to your account.");
    expect(screen.getByText("Invitation ready")).toBeVisible();
    expect(screen.getByRole("button", { name: "Accept invitation" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "No workspace access yet" })).toBeVisible();
  });

  it("lets a new account create its first workspace (self-serve)", async () => {
    requireSession.mockResolvedValue({ displayName: "Dana" });
    listCurrentWorkspaces.mockResolvedValue({ platform_capabilities: [], memberships: [] });

    render(await WorkspacesPage({ searchParams: Promise.resolve({}) }));

    expect(screen.getByRole("heading", { name: "Create your workspace" })).toBeVisible();
    expect(screen.getByLabelText("Workspace name")).toBeRequired();
    expect(screen.getByRole("button", { name: "Create workspace" })).toBeVisible();
  });

  it("offers members another workspace without hiding their list", async () => {
    requireSession.mockResolvedValue({ displayName: "Hamzi" });
    listCurrentWorkspaces.mockResolvedValue({
      platform_capabilities: [],
      memberships: [membership("11111111-1111-4111-8111-111111111111", "Alpha workspace", "tenant_admin")],
    });

    render(await WorkspacesPage({ searchParams: Promise.resolve({ error: "invalid-workspace-name" }) }));

    expect(screen.getByRole("button", { name: /Alpha workspace/ })).toBeVisible();
    expect(screen.getByText("Create another workspace", { selector: "summary" })).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a workspace name of up to 120 characters.");
  });

  it.each([
    ["forbidden", "You do not have permission to open that area."],
    ["invalid-invitation", "That invitation is invalid or has expired."],
    ["invitation-expired", "This invitation has expired. Ask a workspace administrator to send a new one."],
    ["invitation-used", "This invitation has already been used."],
    ["invitation-mismatch", "This invitation was sent to a different email address."],
  ])("maps the %s error to safe feedback", async (error, message) => {
    requireSession.mockResolvedValue({ displayName: "Hamzi" });
    listCurrentWorkspaces.mockResolvedValue({ platform_capabilities: [], memberships: [] });

    render(await WorkspacesPage({ searchParams: Promise.resolve({ error }) }));

    expect(screen.getByRole("alert")).toHaveTextContent(message);
  });
});

describe("global fallback composition", () => {
  it("keeps recovery actions available without exposing private errors", () => {
    const reset = vi.fn();
    const { rerender } = render(<StudioError reset={reset} />);

    expect(screen.getByRole("alert")).not.toHaveTextContent(/stack|token|trace/i);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledOnce();

    rerender(<NotFoundPage />);
    expect(screen.getByRole("link", { name: "Return to Studio" })).toHaveAttribute("href", "/");
  });
});
