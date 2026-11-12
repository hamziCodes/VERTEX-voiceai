// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { controlPlaneRequest, cookieStore, listCurrentWorkspaces, notFound, pathname, redirect, requirePlatform, requireSession } = vi.hoisted(() => ({
  controlPlaneRequest: vi.fn(),
  cookieStore: { delete: vi.fn(), get: vi.fn(), set: vi.fn() },
  listCurrentWorkspaces: vi.fn(),
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  pathname: { value: "/admin" },
  redirect: vi.fn((location: string) => {
    throw new Error(`NEXT_REDIRECT:${location}`);
  }),
  requirePlatform: vi.fn(),
  requireSession: vi.fn(),
}));

vi.mock("next/navigation", () => ({ notFound, redirect, usePathname: () => pathname.value }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("next/headers", () => ({ cookies: vi.fn(async () => cookieStore) }));
vi.mock("@workos-inc/authkit-nextjs", () => ({ getSignInUrl: vi.fn(), signOut: vi.fn(), withAuth: vi.fn() }));
vi.mock("@/auth/session", () => ({ requireSession }));
vi.mock("@/auth/config", () => ({ workspaceCookieSecret: () => `test-${"x".repeat(32)}` }));
vi.mock("@/auth/platform", async () => {
  const permissions = await import("@/auth/platform-permissions");
  return { hasPlatformCapability: permissions.hasPlatformCapability, requirePlatform };
});
vi.mock("@/auth/workspace", async () => {
  const permissions = await import("@/auth/workspace-permissions");
  return { hasWorkspaceCapability: permissions.hasWorkspaceCapability, listCurrentWorkspaces, requireWorkspace: vi.fn() };
});
vi.mock("@/data/control-plane", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/data/control-plane")>()),
  controlPlaneRequest,
}));

import AdminOverviewPage from "@/app/(admin)/admin/page";
import TenantDetailPage from "@/app/(admin)/admin/tenants/[tenantId]/page";
import TenantsPage from "@/app/(admin)/admin/tenants/page";
import WorkspacesPage from "@/app/workspaces/page";
import { ControlPlaneError } from "@/data/control-plane";
import type { TenantDirectoryEntryDto, TenantSummaryDto } from "@/data/schema";
import { AdminNavigation } from "@/features/admin/admin-navigation";

const SESSION = { userId: "user-admin", email: "admin@example.test", displayName: "Ada Admin", accessToken: "header.payload.signature" };
const ADMIN_CAPABILITIES = ["platform_audit:read", "platform_staff:read", "platform_staff:write", "platform_tenant:read"];
const SUPPORT_CAPABILITIES = ["platform_tenant:read"];
const TENANT = "11111111-1111-4111-8111-111111111111";

function platformContext(role: "platform_admin" | "platform_support") {
  return {
    session: SESSION,
    identity: {
      user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      email: SESSION.email,
      role,
      capabilities: role === "platform_admin" ? ADMIN_CAPABILITIES : SUPPORT_CAPABILITIES,
    },
  };
}

const entry = (index: number, agentCount: number | null = 2): TenantDirectoryEntryDto => ({
  tenant_id: `c0000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
  name: `Tenant ${String(index).padStart(2, "0")}`,
  created_at: "2026-02-01T00:00:00Z",
  member_count: 3,
  agent_count: agentCount,
});

const summary: TenantSummaryDto = {
  tenant_id: TENANT,
  name: "Alpha workspace",
  created_at: "2026-01-01T00:00:00Z",
  members_by_role: { tenant_admin: 1, tenant_viewer: 2 },
  agent_count: 4,
  entitlements: {
    max_agents: 3,
    max_concurrent_sessions: 2,
    max_knowledge_bytes: 10485760,
    api_keys_allowed: 2,
    telephony_enabled: false,
    advanced_providers_enabled: false,
    byok_enabled: false,
    allowed_retention_days: [7, 30],
  },
  onboarding_completed_steps: ["business", "use_case"],
};

describe("internal admin area", () => {
  beforeEach(() => {
    pathname.value = "/admin";
    requirePlatform.mockResolvedValue(platformContext("platform_admin"));
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders a distinct internal navigation filtered by platform capabilities", () => {
    const { rerender } = render(<AdminNavigation capabilities={ADMIN_CAPABILITIES} displayName="Ada Admin" role="platform_admin" />);
    const nav = screen.getByRole("navigation", { name: "Wavia admin" });
    expect(within(nav).getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
    for (const name of ["Tenants", "Staff", "Audit"]) expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Workspace" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Build" })).not.toBeInTheDocument();
    expect(screen.getByText("platform admin")).toBeInTheDocument();

    pathname.value = `/admin/tenants/${TENANT}`;
    rerender(<AdminNavigation capabilities={SUPPORT_CAPABILITIES} displayName="Sam Support" role="platform_support" />);
    expect(screen.getByRole("link", { name: "Tenants" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
    expect(screen.queryByRole("link", { name: "Staff" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Audit" })).not.toBeInTheDocument();
  });

  it("shows only reachable destinations on the overview and explains a denial", async () => {
    requirePlatform.mockResolvedValue(platformContext("platform_support"));
    render(await AdminOverviewPage({ searchParams: Promise.resolve({ error: "forbidden" }) }));
    expect(screen.getByRole("heading", { level: 1, name: "Platform overview" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Your platform role cannot open that area.");
    const list = screen.getByRole("list", { name: "Platform areas" });
    expect(within(list).getByRole("link", { name: /Tenants/ })).toHaveAttribute("href", "/admin/tenants");
    expect(within(list).queryByRole("link", { name: /Staff/ })).not.toBeInTheDocument();
    expect(screen.getByText(/do not grant access to customer workspaces/)).toBeInTheDocument();
    expect(screen.getByText("Platform support")).toBeInTheDocument();
  });

  it("renders a bounded, searchable tenant directory with pagination", async () => {
    controlPlaneRequest.mockResolvedValue({ items: Array.from({ length: 25 }, (_, index) => entry(index + 1, index === 0 ? null : 2)), total: 28, limit: 25, offset: 0 });
    render(await TenantsPage({ searchParams: Promise.resolve({ q: "tenant" }) }));

    expect(requirePlatform).toHaveBeenCalledWith("platform_tenant:read");
    expect(controlPlaneRequest.mock.calls[0][0]).toBe("/v1/platform/tenants?limit=25&offset=0&q=tenant");
    expect(controlPlaneRequest.mock.calls[0][1]).toMatchObject({ scope: "platform", selectedTenantId: null });
    expect(screen.getByRole("heading", { level: 1, name: "Tenants" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Search tenants" })).toHaveValue("tenant");
    const table = screen.getByRole("table", { name: "Tenant directory" });
    expect(within(table).getAllByRole("row")).toHaveLength(26);
    expect(within(table).getByRole("link", { name: "Tenant 01" })).toHaveAttribute("href", "/admin/tenants/c0000000-0000-4000-8000-000000000001");
    expect(within(table).getAllByText("Not available")).toHaveLength(1);
    expect(screen.getByText("Showing 1–25 of 28 tenants")).toBeInTheDocument();
    const pages = screen.getByRole("navigation", { name: "Tenant directory pages" });
    expect(within(pages).getByRole("link", { name: "Next page" })).toHaveAttribute("href", "/admin/tenants?q=tenant&page=2");
    expect(within(pages).queryByRole("link", { name: "Previous page" })).not.toBeInTheDocument();
  });

  it("requests later pages and ignores invalid page numbers", async () => {
    controlPlaneRequest.mockResolvedValue({ items: [entry(26)], total: 26, limit: 25, offset: 25 });
    render(await TenantsPage({ searchParams: Promise.resolve({ page: "2" }) }));
    expect(controlPlaneRequest.mock.calls[0][0]).toBe("/v1/platform/tenants?limit=25&offset=25");
    expect(screen.getByRole("link", { name: "Previous page" })).toHaveAttribute("href", "/admin/tenants?page=1");
    cleanup();

    controlPlaneRequest.mockClear();
    controlPlaneRequest.mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });
    render(await TenantsPage({ searchParams: Promise.resolve({ page: "-4" }) }));
    expect(controlPlaneRequest.mock.calls[0][0]).toBe("/v1/platform/tenants?limit=25&offset=0");
  });

  it("distinguishes an empty directory from an empty search", async () => {
    controlPlaneRequest.mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });
    render(await TenantsPage({ searchParams: Promise.resolve({}) }));
    expect(screen.getByRole("heading", { name: "No tenants yet" })).toBeInTheDocument();
    cleanup();

    render(await TenantsPage({ searchParams: Promise.resolve({ q: "zeta" }) }));
    expect(screen.getByRole("heading", { name: "No matching tenants" })).toBeInTheDocument();
    expect(screen.getByText(/No tenant name or ID matches “zeta”/)).toBeInTheDocument();
  });

  it("shows a safe tenant summary and states what is withheld", async () => {
    controlPlaneRequest.mockResolvedValue(summary);
    render(await TenantDetailPage({ params: Promise.resolve({ tenantId: TENANT }) }));

    expect(requirePlatform).toHaveBeenCalledWith("platform_tenant:read");
    expect(controlPlaneRequest.mock.calls[0][0]).toBe(`/v1/platform/tenants/${TENANT}`);
    expect(screen.getByRole("heading", { level: 1, name: "Alpha workspace" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to tenants/ })).toHaveAttribute("href", "/admin/tenants");
    const members = screen.getByRole("list", { name: "Members by role" });
    expect(within(members).getByText("Administrator")).toBeInTheDocument();
    expect(within(members).getByText("Read-only operator")).toBeInTheDocument();
    expect(screen.getByText(/conversations, transcripts, recordings and credentials are not shown/i)).toBeInTheDocument();
    expect(screen.getByText(/recorded in the platform audit/i)).toBeInTheDocument();
    expect(screen.getByText("Telephony")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/token|secret|password/i);
  });

  it("returns not-found for malformed or unknown tenants", async () => {
    await expect(TenantDetailPage({ params: Promise.resolve({ tenantId: "not-a-uuid" }) })).rejects.toThrow("NEXT_NOT_FOUND");
    expect(controlPlaneRequest).not.toHaveBeenCalled();

    controlPlaneRequest.mockRejectedValue(new ControlPlaneError({ code: "upstream_unavailable", message: "missing" }, 404));
    await expect(TenantDetailPage({ params: Promise.resolve({ tenantId: TENANT }) })).rejects.toThrow("NEXT_NOT_FOUND");
  });
});

describe("workspace entry for staff", () => {
  beforeEach(() => {
    requireSession.mockResolvedValue(SESSION);
    cookieStore.get.mockReturnValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const identity = (platformCapabilities: string[]) => ({
    user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    email: SESSION.email,
    is_active: true,
    is_platform_admin: false,
    platform_role: platformCapabilities.length ? "platform_support" : null,
    platform_capabilities: platformCapabilities,
    memberships: [],
  });

  it("offers the internal area only to platform staff", async () => {
    listCurrentWorkspaces.mockResolvedValue(identity(SUPPORT_CAPABILITIES));
    render(await WorkspacesPage({ searchParams: Promise.resolve({}) }));
    expect(screen.getByRole("link", { name: /Open Wavia admin/ })).toHaveAttribute("href", "/admin");
    cleanup();

    listCurrentWorkspaces.mockResolvedValue(identity([]));
    render(await WorkspacesPage({ searchParams: Promise.resolve({}) }));
    expect(screen.queryByRole("link", { name: /Wavia admin/ })).not.toBeInTheDocument();
  });
});
