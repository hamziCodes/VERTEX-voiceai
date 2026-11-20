// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConversationDetailView } from "@/features/conversations/conversation-detail-view";
import { WebhookManager } from "@/features/webhooks/webhook-manager";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const target = {
  target_id: "11111111-1111-4111-8111-111111111111",
  name: "CRM",
  url: "https://crm.example.com/hook",
  state: "active" as const,
  created_at: "2026-11-17T10:00:00Z",
  updated_at: "2026-11-17T10:00:00Z",
  signature_header: "X-Wavia-Signature",
};

describe("WebhookManager", () => {
  it("creates an endpoint and reveals the signing secret once behind an acknowledgement", async () => {
    const onCreate = vi.fn(async () => ({
      state: "created" as const,
      target: { ...target, target_id: "22222222-2222-4222-8222-222222222222", name: "Warehouse", signing_secret: "whsec_example_secret_value_1234" },
    }));
    render(<WebhookManager canManage onCreate={onCreate} onDisable={vi.fn()} targets={[target]} />);

    fireEvent.change(screen.getByLabelText("Endpoint name"), { target: { value: "Warehouse" } });
    fireEvent.change(screen.getByLabelText("Endpoint URL"), { target: { value: "https://wh.example.com/hook" } });
    fireEvent.click(screen.getByRole("button", { name: "Add endpoint" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("whsec_example_secret_value_1234")).toBeVisible();
    const done = within(dialog).getByRole("button", { name: "Done" });
    expect(done).toBeDisabled();
    fireEvent.click(within(dialog).getByLabelText("I have saved this signing secret"));
    fireEvent.click(done);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(onCreate).toHaveBeenCalledWith({ name: "Warehouse", url: "https://wh.example.com/hook" });
  });

  it("shows the refusal reason and hides management for read-only members", async () => {
    const onCreate = vi.fn(async () => ({ state: "error" as const, message: "That endpoint was refused." }));
    const { rerender } = render(<WebhookManager canManage onCreate={onCreate} onDisable={vi.fn()} targets={[]} />);
    expect(screen.getByText("No webhook endpoints yet")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Endpoint name"), { target: { value: "x" } });
    fireEvent.change(screen.getByLabelText("Endpoint URL"), { target: { value: "https://10.0.0.1/" } });
    fireEvent.click(screen.getByRole("button", { name: "Add endpoint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That endpoint was refused.");

    rerender(<WebhookManager canManage={false} onCreate={onCreate} onDisable={vi.fn()} targets={[target]} />);
    expect(screen.queryByRole("button", { name: "Add endpoint" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Disable" })).not.toBeInTheDocument();
  });
});

describe("review decision on a flagged conversation", () => {
  const detail = {
    call_id: "33333333-3333-4333-8333-333333333333",
    agent_id: "44444444-4444-4444-8444-444444444444",
    started_at: "2026-11-17T10:00:00Z",
    ended_at: "2026-11-17T10:01:00Z",
    transport_type: "websocket",
    disposition: "completed",
    end_reason: "user_hangup",
    recording_state: "not_requested",
    turn_count: 1,
    transcript: [{ speaker: "user", text: "Hello", start_ms: 0, end_ms: 500, language: "en", confidence: 1 }],
    usage: { stt_sec: 1, tts_sec: 1, llm_tokens: 0 },
    recording: { state: "not_requested", access: "unavailable" },
  };
  const intelligence = {
    state: "available" as const,
    result: {
      result_id: "55555555-5555-4555-8555-555555555555",
      call_id: detail.call_id,
      extraction: null,
      summary: null,
      verification_issue_codes: [],
      created_at: "2026-11-17T10:01:00Z",
    },
    review: {
      review_id: "66666666-6666-4666-8666-666666666666",
      call_id: detail.call_id,
      result_id: "55555555-5555-4555-8555-555555555555",
      reasons: ["sensitive_field"],
      state: "pending",
      decided_by: null,
      decision_note: null,
      created_at: "2026-11-17T10:01:00Z",
      decided_at: null,
    },
  };

  it("offers approve and reject only to members who can decide", () => {
    const { rerender } = render(
      <ConversationDetailView conversation={detail as never} intelligence={intelligence as never} reviewAction={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Approve and deliver" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Reject" })).toBeVisible();
    expect(screen.getByText(/Webhooks for this call are held/)).toBeVisible();

    rerender(<ConversationDetailView conversation={detail as never} intelligence={intelligence as never} />);
    expect(screen.queryByRole("button", { name: "Approve and deliver" })).not.toBeInTheDocument();
  });
});
