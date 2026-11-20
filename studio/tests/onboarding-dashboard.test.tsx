// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { hasWorkspaceCapability, loadAgents, loadEntitlements, loadOnboarding, requireWorkspace } = vi.hoisted(() => ({
  hasWorkspaceCapability: vi.fn(),
  loadAgents: vi.fn(),
  loadEntitlements: vi.fn(),
  loadOnboarding: vi.fn(),
  requireWorkspace: vi.fn(),
}));

vi.mock("@/auth/workspace", () => ({ hasWorkspaceCapability, requireWorkspace }));
vi.mock("@/features/agents/data", () => ({ loadAgents, loadEntitlements }));
vi.mock("@/features/onboarding/data", () => ({ loadOnboarding }));

import DashboardPage from "@/app/(studio)/dashboard/page";

const context = {
  session: { accessToken: "server-only-test-token", user: { id: "user-test" } },
  membership: {
    tenant_id: "11111111-1111-4111-8111-111111111111",
    tenant_name: "Alpha workspace",
    role: "tenant_admin",
    capabilities: ["onboarding:write", "agent:write", "session:mint"],
  },
};

const onboarding = (requirement_codes: string[]) => ({
  profile: {
    business_name: "Hamzi Stores",
    use_case: "customer_support",
    languages: ["en", "ur"],
    operating_region: requirement_codes.length ? "" : "Pakistan",
    timezone: "Asia/Karachi",
    escalation_email: null,
    completed_steps: [],
  },
  requirement_codes,
});

const agent = (published: boolean) => ({
  agent_id: published ? "11111111-1111-4111-8111-111111111111" : "22222222-2222-4222-8222-222222222222",
  name: published ? "Published support" : "Draft support",
  description: "Answers customer questions",
  languages: ["en"],
  persona: { system_prompt: "Help.", greeting: null, voice_id: "default", voice_by_language: {}, persona_isolation: true },
  providers: { stt: [], llm: [], tts: [], s2s: [] },
  compliance: {},
  draft_revision: 1,
  version: published ? 1 : 0,
  published_at: published ? "2026-11-07T00:00:00Z" : null,
  is_published: published,
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function arrange({
  requirements = [],
  agents = [],
  canEdit = true,
}: {
  requirements?: string[];
  agents?: ReturnType<typeof agent>[];
  canEdit?: boolean;
} = {}) {
  requireWorkspace.mockResolvedValue(context);
  hasWorkspaceCapability.mockImplementation((_capabilities: string[], capability: string) => (
    canEdit || !["onboarding:write", "agent:write"].includes(capability)
  ));
  loadOnboarding.mockResolvedValue(onboarding(requirements));
  loadAgents.mockResolvedValue(agents);
  loadEntitlements.mockResolvedValue({
    max_agents: 3,
    max_concurrent_sessions: 2,
    max_knowledge_bytes: 10_485_760,
    api_keys_allowed: 2,
    telephony_enabled: false,
    advanced_providers_enabled: false,
    byok_enabled: false,
    allowed_retention_days: [7, 30],
  });
}

describe("truthful workspace dashboard", () => {
  it("prioritizes incomplete setup before agent creation and reports real counts", async () => {
    arrange({ requirements: ["operating_region_required"], agents: [] });

    render(await DashboardPage());

    expect(screen.getByRole("heading", { name: "Complete workspace setup" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Continue setup" })).toHaveAttribute("href", "/onboarding");
    expect(screen.getByText("1 item remaining")).toBeVisible();
    expect(screen.getByText("0 of 3")).toBeVisible();
    expect(screen.queryByText(/success rate|minutes saved|calls handled/i)).not.toBeInTheDocument();
  });

  it("directs an editable workspace with a draft to its real build route", async () => {
    arrange({ agents: [agent(false)] });

    render(await DashboardPage());

    expect(screen.getByRole("heading", { name: "Finish your first agent" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Open draft" })).toHaveAttribute(
      "href",
      "/agents/22222222-2222-4222-8222-222222222222/build",
    );
    expect(screen.getByText("0 published")).toBeVisible();
  });

  it("offers the existing test sandbox only after an agent is published", async () => {
    arrange({ agents: [agent(true)] });

    render(await DashboardPage());

    expect(screen.getByRole("heading", { name: "Test your published agent" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Open test sandbox" })).toHaveAttribute(
      "href",
      "/agents/11111111-1111-4111-8111-111111111111/test",
    );
    expect(screen.getByText("1 published")).toBeVisible();
  });

  it("uses review language and withholds creation actions for view-only members", async () => {
    arrange({ requirements: ["operating_region_required"], agents: [], canEdit: false });

    render(await DashboardPage());

    expect(screen.getByRole("link", { name: "Review setup" })).toHaveAttribute("href", "/onboarding");
    expect(screen.queryByRole("link", { name: "Create agent" })).not.toBeInTheDocument();
  });
});
