// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/agents/11111111-1111-4111-8111-111111111111/build" }));

import { AgentWorkspaceTabs } from "@/features/agents/agent-workspace-tabs";

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
});
