// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/agents/11111111-1111-4111-8111-111111111111/build" }));

import { AgentWorkspaceTabs } from "@/features/agents/agent-workspace-tabs";
import { AgentDirectory } from "@/features/agents/agent-directory";
import type { AgentDto } from "@/features/agents/types";

const agentBase: AgentDto = {
  agent_id: "11111111-1111-4111-8111-111111111111",
  name: "Zeta support",
  description: "Answers customer questions",
  languages: ["en"],
  persona: { system_prompt: "Help clearly.", greeting: "Hello", voice_id: "default", voice_by_language: {}, persona_isolation: true },
  providers: { stt: [], llm: [], tts: [], s2s: [] },
  compliance: { tier: "standard" },
  draft_revision: 2,
  version: 2,
  published_at: "2026-11-01T00:00:00Z",
  is_published: true,
};

const draftAgent: AgentDto = {
  ...agentBase,
  agent_id: "22222222-2222-4222-8222-222222222222",
  name: "Alpha intake",
  description: "Collects appointment details",
  version: 0,
  published_at: null,
  is_published: false,
};

afterEach(cleanup);

describe("Phase 13G Studio visual pilot", () => {
  it("links only real agent routes and marks the route-derived tab current", () => {
    render(<AgentWorkspaceTabs agentId="11111111-1111-4111-8111-111111111111" />);

    expect(screen.getByRole("link", { name: "Persona" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Test sandbox" })).toHaveAttribute(
      "href",
      "/agents/11111111-1111-4111-8111-111111111111/test",
    );
    expect(screen.getAllByRole("link")).toHaveLength(2);
    expect(screen.queryByRole("link", { name: "Tools" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Live monitor" })).not.toBeInTheDocument();
  });

  it("searches and filters agents using only existing agent fields", () => {
    render(<AgentDirectory agents={[agentBase, draftAgent]} canCreate canEdit maxAgents={5} />);

    expect(screen.getAllByRole("row")[1]).toHaveTextContent("Alpha intake");
    fireEvent.change(screen.getByRole("searchbox", { name: "Search agents" }), { target: { value: "zeta" } });
    expect(screen.getByText("Zeta support")).toBeVisible();
    expect(screen.queryByText("Alpha intake")).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search agents" }), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "draft" } });
    expect(screen.getByText("Alpha intake")).toBeVisible();
    expect(screen.queryByText("Zeta support")).not.toBeInTheDocument();
  });

  it("sorts deterministically and distinguishes an empty filter result", () => {
    render(<AgentDirectory agents={[draftAgent, agentBase]} canCreate canEdit maxAgents={5} />);

    fireEvent.change(screen.getByLabelText("Sort"), { target: { value: "name-desc" } });
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("Zeta support");

    fireEvent.change(screen.getByRole("searchbox", { name: "Search agents" }), { target: { value: "missing" } });
    expect(screen.getByText("No agents match these filters.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByText("Alpha intake")).toBeVisible();
  });

  it("preserves role-aware actions and the true empty-workspace state", () => {
    const { rerender } = render(<AgentDirectory agents={[agentBase]} canCreate={false} canEdit={false} maxAgents={1} />);

    expect(screen.getByRole("link", { name: "View agent" })).toBeVisible();
    expect(screen.queryByRole("link", { name: "Create agent" })).not.toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /Zeta support/ })).getByText("Published · v2")).toBeVisible();

    rerender(<AgentDirectory agents={[]} canCreate canEdit maxAgents={5} />);
    expect(screen.getByText("No agents yet")).toBeVisible();
    expect(screen.getByRole("link", { name: "Create agent" })).toBeVisible();
  });
});
