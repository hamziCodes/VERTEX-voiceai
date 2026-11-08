// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/test" }));

import { TestAgentSelector } from "@/features/voice-test/test-agent-selector";
import { WorkspaceNavigation } from "@/features/workspaces/workspace-navigation";
import type { AgentDto } from "@/features/agents/types";

const agent = (name: string, published: boolean, id: string): AgentDto => ({
  agent_id: id,
  name,
  description: `${name} description`,
  languages: ["en"],
  persona: { system_prompt: "Help.", greeting: null, voice_id: "default", voice_by_language: {}, persona_isolation: true },
  providers: { stt: [], llm: [], tts: [], s2s: [] },
  compliance: {},
  draft_revision: 1,
  version: published ? 1 : 0,
  published_at: published ? "2026-11-07T00:00:00Z" : null,
  is_published: published,
});

afterEach(cleanup);

describe("global test agent selector", () => {
  it("renders an honest empty workspace state", () => {
    render(<TestAgentSelector agents={[]} canStart />);

    expect(screen.getByRole("heading", { name: "No agents available" })).toBeVisible();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("keeps drafts visible with an explicit disabled reason", () => {
    render(<TestAgentSelector agents={[agent("Draft intake", false, "11111111-1111-4111-8111-111111111111")]} canStart />);

    const row = screen.getByRole("listitem", { name: /Draft intake/ });
    expect(within(row).getByText("Publish this agent before opening the voice sandbox.")).toBeVisible();
    expect(within(row).queryByRole("link")).not.toBeInTheDocument();
  });

  it("sorts deterministically and links only published agents to their real sandboxes", () => {
    render(<TestAgentSelector agents={[
      agent("Zulu support", true, "22222222-2222-4222-8222-222222222222"),
      agent("Alpha support", true, "11111111-1111-4111-8111-111111111111"),
      agent("Beta draft", false, "33333333-3333-4333-8333-333333333333"),
    ]} canStart />);

    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Alpha support");
    expect(items[1]).toHaveTextContent("Beta draft");
    expect(items[2]).toHaveTextContent("Zulu support");
    expect(screen.getByRole("link", { name: "Open Alpha support test sandbox" })).toHaveAttribute(
      "href",
      "/agents/11111111-1111-4111-8111-111111111111/test",
    );
    expect(screen.getAllByRole("link")).toHaveLength(2);
  });

  it("lets viewers review a published test page without claiming they can start it", () => {
    render(<TestAgentSelector agents={[agent("Store support", true, "11111111-1111-4111-8111-111111111111")]} canStart={false} />);

    expect(screen.getByText("Your role can review test readiness but cannot start a voice session.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Review Store support test status" })).toHaveAttribute(
      "href",
      "/agents/11111111-1111-4111-8111-111111111111/test",
    );
  });

  it("routes the sidebar Test entry to the global selector", () => {
    render(<WorkspaceNavigation capabilities={["session:read"]} role="tenant_viewer" />);

    expect(screen.getByRole("link", { name: "Test" })).toHaveAttribute("href", "/test");
    expect(screen.getByRole("link", { name: "Test" })).toHaveAttribute("aria-current", "page");
  });
});
