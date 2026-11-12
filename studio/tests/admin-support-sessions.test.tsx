// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { controlPlaneRequest, notFound, push, redirect, refresh, requirePlatform } = vi.hoisted(() => ({
  controlPlaneRequest: vi.fn(),
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  push: vi.fn(),
  redirect: vi.fn((location: string) => {
    throw new Error(`NEXT_REDIRECT:${location}`);
  }),
  refresh: vi.fn(),
  requirePlatform: vi.fn(),
}));

vi.mock("next/navigation", () => ({ notFound, redirect, usePathname: () => "/admin/support-sessions", useRouter: () => ({ push, refresh }) }));
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

import SupportSessionPage from "@/app/(admin)/admin/support-sessions/[sessionId]/page";
import SupportSessionsPage from "@/app/(admin)/admin/support-sessions/page";
import TenantDetailPage from "@/app/(admin)/admin/tenants/[tenantId]/page";
import { ControlPlaneError } from "@/data/control-plane";
import type { SupportSessionDto } from "@/data/schema";
import { AdminNavigation } from "@/features/admin/admin-navigation";
import { StartSupportSession } from "@/features/admin/start-support-session";

const SUPPORT = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const ADMIN = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const TENANT = "11111111-1111-4111-8111-111111111111";
const SESSION = "33333333-3333-4333-8333-333333333333";
const SUPPORT_CAPABILITIES = ["platform_support_session:read", "platform_support_session:write", "platform_tenant:read"];
const ADMIN_CAPABILITIES = [
  "platform_audit:read",
  "platform_operations:read",
  "platform_staff:read",
  "platform_staff:write",
  "platform_support_session:manage",
  "platform_support_session:read",
  "platform_support_session:write",
  "platform_tenant:read",
];

function staff(role: "platform_admin" | "platform_support") {
  const support = role === "platform_support";
  return {
    session: { userId: "user", email: "staff@example.test", displayName: "Staff", accessToken: "a.b.c" },
    identity: { user_id: support ? SUPPORT : ADMIN, email: "staff@example.test", role, capabilities: support ? SUPPORT_CAPABILITIES : ADMIN_CAPABILITIES },
  };
}

const supportSession = (overrides: Partial<SupportSessionDto> = {}): SupportSessionDto => ({
  session_id: SESSION,
  actor_user_id: SUPPORT,
  actor_email: "support@example.test",
  tenant_id: TENANT,
  tenant_name: "Alpha workspace",
  reason: "Customer ticket about agent setup",
  reference: "TICKET-1042",
  scopes: ["configuration", "readiness"],
  created_at: "2026-11-12T10:00:00Z",
  expires_at: "2026-11-12T10:30:00Z",
  ended_at: null,
  ended_by: null,
  end_reason: null,
  state: "active",
  ...overrides,
});

const configuration = {
  session: supportSession(),
  agents: [{
    agent_id: "44444444-4444-4444-8444-444444444444",
    name: "Front desk",
    description: "Answers booking questions",
    languages: ["en", "ur"],
    version: 3,
    draft_revision: 5,
    is_published: true,
    published_at: "2026-11-01T09:00:00Z",
    provider_route_counts: { stt: 2, llm: 2, tts: 2, s2s: 0 },
    knowledge_base_count: 1,
    tool_count: 2,
    mcp_server_count: 0,
    telephony_configured: false,
    compliance_tier: "standard",
  }],
  knowledge_bases: [{
    knowledge_base_id: "55555555-5555-4555-8555-555555555555",
    name: "Booking FAQ",
    status: "active",
    source_count: 4,
    ready_source_count: 3,
    updated_at: "2026-11-02T09:00:00Z",
  }],
};

const readiness = {
  session: supportSession(),
  onboarding: { completed_steps: ["business", "use_case"], use_case: "customer_support", languages: ["en"], timezone: "UTC" },
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
  telephony: { trunk_configured: false, telephony_entitled: false, carrier_health: "not_measured" },
};

function routeResponses(map: Record<string, unknown>) {
  controlPlaneRequest.mockImplementation(async (path: string) => {
    for (const [suffix, value] of Object.entries(map)) {
      if (path.endsWith(suffix)) {
        if (value instanceof Error) throw value;
        return value;
      }
    }
    throw new Error(`unexpected ${path}`);
  });
}

describe("support sessions", () => {
  beforeEach(() => {
    requirePlatform.mockResolvedValue(staff("platform_support"));
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("adds Support sessions to the internal navigation by capability", () => {
    render(<AdminNavigation capabilities={SUPPORT_CAPABILITIES} role="platform_support" />);
    expect(screen.getByRole("link", { name: "Support sessions" })).toHaveAttribute("aria-current", "page");
    cleanup();
    render(<AdminNavigation capabilities={["platform_tenant:read"]} role="platform_support" />);
    expect(screen.queryByRole("link", { name: "Support sessions" })).not.toBeInTheDocument();
  });

  it("offers a reasoned, scoped, expiring start from the tenant summary only with write capability", async () => {
    routeResponses({
      [`/v1/platform/tenants/${TENANT}`]: {
        tenant_id: TENANT,
        name: "Alpha workspace",
        created_at: "2026-01-01T00:00:00Z",
        members_by_role: { tenant_admin: 1 },
        agent_count: 1,
        entitlements: null,
        onboarding_completed_steps: [],
      },
    });
    render(await TenantDetailPage({ params: Promise.resolve({ tenantId: TENANT }) }));
    expect(screen.getByRole("button", { name: "Start support session" })).toBeInTheDocument();
    cleanup();

    requirePlatform.mockResolvedValue({ ...staff("platform_support"), identity: { ...staff("platform_support").identity, capabilities: ["platform_tenant:read"] } });
    render(await TenantDetailPage({ params: Promise.resolve({ tenantId: TENANT }) }));
    expect(screen.queryByRole("button", { name: "Start support session" })).not.toBeInTheDocument();
  });

  it("starts a session with reason, scopes and duration, then opens it", async () => {
    const onStart = vi.fn()
      .mockResolvedValueOnce({ ok: false, code: "conflict", message: "You already have an active support session for this tenant." })
      .mockResolvedValueOnce({ ok: true, data: supportSession() });
    render(<StartSupportSession onStart={onStart} tenantId={TENANT} tenantName="Alpha workspace" />);

    fireEvent.click(screen.getByRole("button", { name: "Start support session" }));
    const dialog = screen.getByRole("dialog", { name: "Start a support session" });
    expect(within(dialog).getByLabelText("Reason")).toHaveFocus();
    expect(within(dialog).getByRole("checkbox", { name: /Configuration/ })).toBeChecked();
    expect(within(dialog).getByRole("checkbox", { name: /Readiness/ })).not.toBeChecked();
    expect(within(dialog).getByLabelText("Duration")).toHaveValue("30");
    expect(within(dialog).getByText(/read-only/i)).toBeInTheDocument();
    const submit = within(dialog).getByRole("button", { name: "Start session" });
    expect(submit).toBeDisabled();

    fireEvent.change(within(dialog).getByLabelText("Reason"), { target: { value: "Customer ticket about agent setup" } });
    fireEvent.click(within(dialog).getByRole("checkbox", { name: /Configuration/ }));
    expect(submit).toBeDisabled();
    fireEvent.click(within(dialog).getByRole("checkbox", { name: /Readiness/ }));
    fireEvent.change(within(dialog).getByLabelText("Ticket reference (optional)"), { target: { value: "TICKET-1042" } });
    fireEvent.change(within(dialog).getByLabelText("Duration"), { target: { value: "15" } });
    fireEvent.click(submit);

    await waitFor(() => expect(within(dialog).getByRole("alert")).toHaveTextContent("already have an active support session"));
    expect(onStart).toHaveBeenCalledWith({
      tenantId: TENANT,
      reason: "Customer ticket about agent setup",
      reference: "TICKET-1042",
      scopes: ["readiness"],
      durationMinutes: 15,
    });
    fireEvent.click(submit);
    await waitFor(() => expect(push).toHaveBeenCalledWith(`/admin/support-sessions/${SESSION}`));
  });

  it("shows a persistent read-only banner and only the granted, audited scopes to the owner", async () => {
    routeResponses({
      [`/v1/platform/support-sessions/${SESSION}`]: supportSession(),
      "/configuration": configuration,
      "/readiness": readiness,
    });
    render(await SupportSessionPage({ params: Promise.resolve({ sessionId: SESSION }) }));

    expect(requirePlatform).toHaveBeenCalledWith("platform_support_session:read");
    const banner = screen.getByRole("region", { name: "Support session" });
    expect(banner).toHaveTextContent("Read-only");
    expect(banner).toHaveTextContent("Alpha workspace");
    expect(banner).toHaveTextContent("Ends 12 Nov 2026, 10:30 UTC");
    expect(within(banner).getByRole("button", { name: "End session" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Agents" })).toHaveTextContent("Front desk");
    expect(screen.getByRole("table", { name: "Knowledge bases" })).toHaveTextContent("Booking FAQ");
    expect(screen.getByRole("heading", { name: "Readiness" })).toBeInTheDocument();
    expect(screen.getByText(/Each view of this page is recorded in the platform audit/)).toBeInTheDocument();
    expect(controlPlaneRequest.mock.calls.map((call) => call[0])).toEqual([
      `/v1/platform/support-sessions/${SESSION}`,
      `/v1/platform/support-sessions/${SESSION}/configuration`,
      `/v1/platform/support-sessions/${SESSION}/readiness`,
    ]);
  });

  it("loads no tenant data for another staff member or a closed session", async () => {
    requirePlatform.mockResolvedValue(staff("platform_admin"));
    routeResponses({ [`/v1/platform/support-sessions/${SESSION}`]: supportSession() });
    render(await SupportSessionPage({ params: Promise.resolve({ sessionId: SESSION }) }));
    expect(screen.getByText(/Only support@example.test can view tenant data/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "End session" })).toBeInTheDocument();
    expect(controlPlaneRequest).toHaveBeenCalledTimes(1);
    cleanup();

    controlPlaneRequest.mockReset();
    requirePlatform.mockResolvedValue(staff("platform_support"));
    routeResponses({ [`/v1/platform/support-sessions/${SESSION}`]: supportSession({ state: "expired" }) });
    render(await SupportSessionPage({ params: Promise.resolve({ sessionId: SESSION }) }));
    expect(screen.getByRole("heading", { name: "Support session expired" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Support session" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "End session" })).not.toBeInTheDocument();
    expect(controlPlaneRequest).toHaveBeenCalledTimes(1);
  });

  it("treats a session that closes mid-load as closed and hides partial data", async () => {
    routeResponses({
      [`/v1/platform/support-sessions/${SESSION}`]: supportSession(),
      "/configuration": configuration,
      "/readiness": new ControlPlaneError({ code: "upstream_unavailable", message: "gone" }, 410),
    });
    render(await SupportSessionPage({ params: Promise.resolve({ sessionId: SESSION }) }));
    expect(screen.getByRole("heading", { name: "Support session closed" })).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Agents" })).not.toBeInTheDocument();
  });

  it("lists active and recent sessions with end controls by ownership", async () => {
    const mine = supportSession();
    const theirs = supportSession({ session_id: "66666666-6666-4666-8666-666666666666", actor_user_id: ADMIN, actor_email: "admin@example.test", tenant_name: "Beta workspace" });
    const closed = supportSession({ session_id: "77777777-7777-4777-8777-777777777777", state: "ended", ended_at: "2026-11-12T10:10:00Z", ended_by: SUPPORT });
    controlPlaneRequest.mockImplementation(async (path: string) => (path.includes("state=active") ? [mine, theirs] : [mine, theirs, closed]));
    render(await SupportSessionsPage());

    const active = screen.getByRole("table", { name: "Active support sessions" });
    const mineRow = within(active).getByRole("row", { name: /Alpha workspace/ });
    expect(within(mineRow).getByRole("link", { name: /Open/ })).toHaveAttribute("href", `/admin/support-sessions/${SESSION}`);
    expect(within(mineRow).getByRole("button", { name: /End/ })).toBeInTheDocument();
    const theirsRow = within(active).getByRole("row", { name: /Beta workspace/ });
    expect(within(theirsRow).queryByRole("button", { name: /End/ })).not.toBeInTheDocument();
    const recent = screen.getByRole("table", { name: "Recent support sessions" });
    expect(within(recent).getByText("Ended")).toBeInTheDocument();
    expect(within(recent).getAllByText("Configuration, Readiness").length).toBeGreaterThan(0);
  });
});
