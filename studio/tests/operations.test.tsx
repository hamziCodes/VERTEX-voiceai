// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { requireWorkspace, conversationsData, getUsage, getAuditEvents } = vi.hoisted(() => ({
  requireWorkspace: vi.fn(),
  conversationsData: { listConversations: vi.fn(), getConversation: vi.fn(), getConversationIntelligence: vi.fn() },
  getUsage: vi.fn(),
  getAuditEvents: vi.fn(),
}));
vi.mock("next/navigation", () => ({ redirect: vi.fn(), usePathname: () => "/conversations" }));
vi.mock("@/auth/workspace", () => ({ requireWorkspace }));
vi.mock("@/features/conversations/data", () => conversationsData);
vi.mock("@/features/usage/data", () => ({ getUsage }));
vi.mock("@/features/audit/data", () => ({ getAuditEvents }));

import AuditPage from "@/app/(studio)/settings/audit/page";
import UsagePage from "@/app/(studio)/settings/usage/page";
import ConversationDetailPage from "@/app/(studio)/conversations/[callId]/page";
import ConversationsPage from "@/app/(studio)/conversations/page";

import { AuditView } from "@/features/audit/audit-view";
import { ConversationDetailView } from "@/features/conversations/conversation-detail-view";
import { ConversationListView } from "@/features/conversations/conversation-list-view";
import { OperationsNavigation } from "@/features/operations/operations-navigation";
import { UsageView } from "@/features/usage/usage-view";

afterEach(cleanup);

const calls = [
  {
    call_id: "11111111-1111-4111-8111-111111111111",
    agent_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    started_at: "2026-11-04T09:00:00Z",
    ended_at: "2026-11-04T09:02:00Z",
    transport_type: "websocket",
    disposition: "completed",
    recording_state: "available",
    turn_count: 4,
  },
  {
    call_id: "22222222-2222-4222-8222-222222222222",
    agent_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    started_at: "2026-11-04T08:00:00Z",
    ended_at: null,
    transport_type: "sip",
    disposition: "failed",
    recording_state: "consent_blocked",
    turn_count: 0,
  },
];

describe("ConversationListView", () => {
  it("renders an honest empty-tenant state", () => {
    render(<ConversationListView page={{ items: [], next_cursor: null }} />);

    expect(screen.getByText(/No conversations have been recorded for this workspace/i)).toBeVisible();
    expect(screen.queryByText(/success rate/i)).not.toBeInTheDocument();
  });

  it("renders durable calls, filters only the loaded page, and preserves the next cursor", () => {
    const { container } = render(<ConversationListView page={{ items: calls, next_cursor: "cursor-page-two" }} />);
    const view = within(container);

    expect(view.getByText(/Filters apply to this loaded page/i)).toBeVisible();
    fireEvent.change(view.getByLabelText("Transport"), { target: { value: "sip" } });

    expect(view.getAllByText("SIP")).toHaveLength(2);
    expect(view.queryByRole("cell", { name: "Web" })).not.toBeInTheDocument();
    expect(view.getByRole("link", { name: /Next page/i })).toHaveAttribute(
      "href",
      "/conversations?cursor=cursor-page-two",
    );
  });
});

describe("ConversationDetailView", () => {
  const detail = {
    ...calls[0],
    end_reason: "completed",
    transcript: [
      { speaker: "user", text: "I need help", start_ms: 0, end_ms: 500, language: "en", confidence: 0.98 },
      { speaker: "assistant", text: "I can help", start_ms: 600, end_ms: 1100, language: "en", confidence: 1 },
    ],
    usage: { stt_sec: 1.1, tts_sec: 1.2, llm_tokens: 24 },
    recording: { state: "available", access: "gated", duration_sec: 2 },
  };

  it("shows transcript and pending review without exposing storage references", () => {
    const { container } = render(
      <ConversationDetailView
        conversation={detail}
        intelligence={{
          state: "available",
          result: {
            result_id: "33333333-3333-4333-8333-333333333333",
            call_id: detail.call_id,
            extraction: null,
            summary: {
              executive_summary: "Customer requested assistance.",
              key_takeaways: ["Asked for help"],
              sentiment_trajectory: [],
              source_turn_ids: [0],
              provider_id: "groq",
              model_id: "openai/gpt-oss-120b",
            },
            verification_issue_codes: ["sensitive_field"],
            created_at: "2026-11-04T09:03:00Z",
          },
          review: {
            review_id: "44444444-4444-4444-8444-444444444444",
            call_id: detail.call_id,
            result_id: "33333333-3333-4333-8333-333333333333",
            reasons: ["sensitive_field"],
            state: "pending",
            decided_by: null,
            decision_note: null,
            created_at: "2026-11-04T09:03:00Z",
            decided_at: null,
          },
        }}
      />,
    );

    expect(container).toHaveTextContent("I need help");
    // Regression (Stage 3): Studio read `summary.text`, which the engine never
    // sends, so every real summary showed "No durable summary was produced".
    expect(within(container).getByText("Customer requested assistance.")).toBeVisible();
    expect(within(container).getByText("Asked for help")).toBeVisible();
    expect(container).toHaveTextContent("Generated by groq.");
    expect(within(container).getByText(/Review required/i)).toBeVisible();
    expect(within(container).getByText(/Recording available; access is gated/i)).toBeVisible();
    expect(container.textContent).not.toContain("s3://");
    expect(container.textContent).not.toContain(detail.call_id);
  });

  it.each([
    ["not_requested", "Recording was not requested"],
    ["failed", "Recording failed"],
    ["deleted", "Recording was deleted"],
    ["consent_blocked", "Recording was blocked by consent policy"],
  ])("renders the source recording state %s without inventing availability", (state, label) => {
    const { container } = render(
      <ConversationDetailView
        conversation={{ ...detail, recording_state: state, recording: { state, access: "unavailable" } }}
        intelligence={{ state: "unavailable", result: null, review: null }}
      />,
    );

    const view = within(container);
    expect(view.getByText(new RegExp(label, "i"))).toBeVisible();
    expect(view.getByText(/Intelligence is not available/i)).toBeVisible();
  });

  it("labels a mock-provider summary and shows extracted fields honestly", () => {
    const { container } = render(
      <ConversationDetailView
        conversation={detail}
        intelligence={{
          state: "available",
          result: {
            result_id: "55555555-5555-4555-8555-555555555555",
            call_id: detail.call_id,
            extraction: { fields: { caller_name: { value: null, confidence: 0 }, preferred_day: { value: "Tuesday", confidence: 0.9 } } },
            summary: { executive_summary: "Mock summary (no model was called).", key_takeaways: [], source_turn_ids: [0], provider_id: "mock", model_id: "mock-transcript-quotes" },
            verification_issue_codes: [],
            created_at: "2026-11-04T09:03:00Z",
          },
          review: null,
        }}
      />,
    );

    const view = within(container);
    expect(view.getByText(/development mock provider; no model was called/i)).toBeVisible();
    expect(view.getByText("Not stated")).toBeVisible();
    expect(view.getByText("Tuesday")).toBeVisible();
  });

  it("labels a source-reported pending intelligence state without inventing a result", () => {
    const { container } = render(
      <ConversationDetailView
        conversation={detail}
        intelligence={{ state: "pending", result: null, review: null }}
      />,
    );

    expect(within(container).getByText(/Intelligence processing is pending/i)).toBeVisible();
    expect(container.textContent).not.toContain("No durable summary was produced");
  });
});

describe("UsageView", () => {
  it("shows server totals and a hard-cap warning without inventing prices or period dates", () => {
    render(
      <UsageView
        usage={{
          status: "success",
          tenant_id: "tenant-hidden",
          quota: {
            max_concurrent: 2,
            max_minutes_month: 100,
            max_llm_tokens_month: 1000,
            current_concurrent: 2,
            current_monthly_minutes: 100,
            current_monthly_llm_tokens: 1000,
            soft_cap_percent: 80,
            hard_cap_percent: 100,
          },
          totals: { stt_sec: 30, tts_sec: 20, llm_tokens: 1000, agent_sec: 60, telephony_sec: 0 },
        }}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(/hard cap reached/i);
    expect(screen.getByText(/Exact period start and end dates are not supplied/i)).toBeVisible();
    expect(screen.queryByText(/price|cost|saving/i)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toContain("tenant-hidden");
  });
});

describe("AuditView", () => {
  it("renders durable degraded-provider evidence and hides tenant/network identifiers", () => {
    const { container } = render(
      <AuditView
        events={[{
          id: "55555555-5555-4555-8555-555555555555",
          tenant_id: "tenant-hidden",
          actor_id: "actor-hidden",
          actor_type: "system",
          action: "provider.degraded",
          resource_type: "provider",
          resource_id: "groq-secret-resource-id",
          detail: {},
          ip: "192.0.2.1",
          user_agent: "private-agent",
          created_at: "2026-11-04T09:04:00Z",
        }]}
      />,
    );

    expect(within(container).getByText("provider.degraded")).toBeVisible();
    expect(container.textContent).not.toContain("tenant-hidden");
    expect(container.textContent).not.toContain("192.0.2.1");
    expect(container.textContent).not.toContain("groq-secret-resource-id");
  });
});

describe("OperationsNavigation", () => {
  it("shows viewer conversation and usage access without audit access", () => {
    const { container } = render(
      <OperationsNavigation capabilities={["conversation:read", "usage:read"]} />,
    );
    const navigation = within(container);

    expect(navigation.getByRole("link", { name: "Conversations" })).toBeVisible();
    expect(navigation.getByRole("link", { name: "Usage" })).toBeVisible();
    expect(navigation.queryByRole("link", { name: "Audit" })).not.toBeInTheDocument();
  });

  it("shows compliance conversation and audit access without usage access", () => {
    const { container } = render(
      <OperationsNavigation capabilities={["conversation:read", "audit:read"]} />,
    );
    const navigation = within(container);

    expect(navigation.getByRole("link", { name: "Conversations" })).toBeVisible();
    expect(navigation.getByRole("link", { name: "Audit" })).toBeVisible();
    expect(navigation.queryByRole("link", { name: "Usage" })).not.toBeInTheDocument();
  });
});

describe("composed operations surfaces", () => {
  const usage = {
    status: "success",
    tenant_id: "tenant-hidden",
    quota: { max_concurrent: 10, max_minutes_month: 1000, max_llm_tokens_month: 100000, current_concurrent: 1, current_monthly_minutes: 12.5, current_monthly_llm_tokens: 2400, soft_cap_percent: 80, hard_cap_percent: 100 },
    totals: { stt_sec: 300, tts_sec: 240, llm_tokens: 2400, agent_sec: 750, telephony_sec: 0 },
  };
  const workspace = { session: { accessToken: "offline" }, membership: { tenant_id: "66666666-6666-4666-8666-666666666666", capabilities: ["conversation:read", "usage:read", "audit:read"] } };

  it("lists conversations in a labelled table with fixed-format times and distinct empty-by-filter text", () => {
    const { container } = render(<ConversationListView page={{ items: calls, next_cursor: null }} />);

    expect(container.querySelectorAll("[style]")).toHaveLength(0);
    const table = screen.getByRole("table", { name: "Conversations" });
    expect(within(table).getByText("4 Nov 2026, 09:00 UTC")).toBeVisible();
    expect(within(table).getByText("Completed")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Disposition"), { target: { value: "failed" } });
    fireEvent.change(screen.getByLabelText("Transport"), { target: { value: "websocket" } });
    expect(screen.getByText("No conversations on this page match the selected filters.")).toBeVisible();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("labels transcript speakers and shows recording and intelligence states as badges", () => {
    const { container } = render(
      <ConversationDetailView
        conversation={{ ...calls[0], end_reason: "completed", transcript: [
          { speaker: "user", text: "I need help", start_ms: 0, end_ms: 500, language: "en", confidence: 0.98 },
          { speaker: "assistant", text: "I can help", start_ms: 600, end_ms: 1100, language: "en", confidence: 1 },
        ], usage: {}, recording: { state: "available", access: "gated" } }}
        intelligence={{ state: "pending", result: null, review: null }}
      />,
    );

    expect(container.querySelectorAll("[style]")).toHaveLength(0);
    const transcript = screen.getByRole("region", { name: "Transcript" });
    const turns = within(transcript).getAllByRole("listitem");
    expect(turns[0]).toHaveTextContent("Caller");
    expect(turns[1]).toHaveTextContent("Agent");
    expect(within(screen.getByRole("region", { name: "Recording" })).getByText("Available")).toBeVisible();
    expect(within(screen.getByRole("region", { name: "Post-call intelligence" })).getByText("Pending")).toBeVisible();
  });

  it("exposes usage as accessible meters with value and limit text", () => {
    const { container } = render(<UsageView usage={usage} />);

    expect(container.querySelectorAll("[style]")).toHaveLength(0);
    const minutes = screen.getByRole("meter", { name: "Monthly minutes" });
    expect(minutes).toHaveAttribute("aria-valuenow", "12.5");
    expect(minutes).toHaveAttribute("aria-valuemax", "1000");
    expect(screen.getByText("12.5 of 1,000")).toBeVisible();
    expect(screen.getByRole("meter", { name: "Monthly LLM tokens" })).toHaveAttribute("aria-valuenow", "2400");
    expect(within(screen.getByRole("region", { name: "Measured totals" })).getByText("Speech-to-text seconds")).toBeVisible();
  });

  it("shows audit events in a labelled table with fixed-format times", () => {
    render(<AuditView events={[{ id: "55555555-5555-4555-8555-555555555555", tenant_id: "t", actor_id: "a", actor_type: "system", action: "provider.degraded", resource_type: "provider", resource_id: "r", detail: {}, ip: null, user_agent: null, created_at: "2026-11-04T09:04:00Z" }]} />);

    const table = screen.getByRole("table", { name: "Audit events" });
    expect(within(table).getByText("4 Nov 2026, 09:04 UTC")).toBeVisible();
  });

  it("gives every operate page a shared header and the operations tabs", async () => {
    requireWorkspace.mockResolvedValue(workspace);
    conversationsData.listConversations.mockResolvedValue({ items: calls, next_cursor: null });
    getUsage.mockResolvedValue(usage);
    getAuditEvents.mockResolvedValue([]);
    conversationsData.getConversation.mockResolvedValue({ ...calls[0], end_reason: "completed", transcript: [], usage: {}, recording: { state: "not_requested", access: "unavailable" } });
    conversationsData.getConversationIntelligence.mockResolvedValue({ state: "unavailable", result: null, review: null });

    const pages: Array<[Promise<React.ReactElement>, string]> = [
      [ConversationsPage({ searchParams: Promise.resolve({}) }), "Conversation history"],
      [ConversationDetailPage({ params: Promise.resolve({ callId: calls[0].call_id }) }), "Conversation detail"],
      [UsagePage(), "Usage and limits"],
      [AuditPage(), "Audit history"],
    ];
    for (const [page, title] of pages) {
      const { container } = render(await page);
      expect(screen.getByRole("heading", { level: 1, name: title })).toBeVisible();
      expect(screen.getByRole("navigation", { name: "Operations" })).toBeVisible();
      expect(container.querySelectorAll("[style]")).toHaveLength(0);
      cleanup();
    }
    expect(requireWorkspace).toHaveBeenCalledWith("conversation:read");
    expect(requireWorkspace).toHaveBeenCalledWith("usage:read");
    expect(requireWorkspace).toHaveBeenCalledWith("audit:read");
  });
});
