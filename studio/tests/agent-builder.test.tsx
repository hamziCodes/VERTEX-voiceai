// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentCreationWizard } from "@/features/agents/agent-creation-wizard";
import { AgentDraftEditor } from "@/features/agents/agent-draft-editor";
import type { AgentDto, AgentTemplateDto } from "@/features/agents/types";
import { OnboardingForm } from "@/features/onboarding/onboarding-form";

const agent: AgentDto = {
  agent_id: "11111111-1111-4111-8111-111111111111",
  name: "Store assistant",
  description: "Answers order questions",
  languages: ["en"],
  persona: {
    system_prompt: "Help customers clearly.",
    greeting: "Hello, how can I help?",
    voice_id: "default",
    voice_by_language: {},
    persona_isolation: true,
  },
  providers: { stt: [], llm: [], tts: [], s2s: [] },
  compliance: { tier: "standard", hipaa_baa_acknowledged: false },
  draft_revision: 3,
  version: 1,
  published_at: null,
  is_published: false,
};

const templates: AgentTemplateDto[] = [
  {
    template_id: "retail_customer_service",
    name: "Retail customer care",
    description: "Order and return support",
    languages: ["en"],
    persona: agent.persona,
    providers: agent.providers,
    compliance: agent.compliance,
  },
];

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("guided onboarding", () => {
  it("resumes saved fields and shows only API-provided requirements", async () => {
    const saveAction = vi.fn().mockResolvedValue({ state: "saved" as const });
    render(
      <OnboardingForm
        initial={{
          business_name: "Hamzi Stores",
          use_case: "customer_support",
          languages: ["en", "ur"],
          operating_region: "Pakistan",
          timezone: "Asia/Karachi",
          escalation_email: null,
          completed_steps: ["business"],
        }}
        requirementCodes={["operating_region_required"]}
        canEdit
        saveAction={saveAction}
      />,
    );

    expect(screen.getByLabelText("Business name")).toHaveValue("Hamzi Stores");
    expect(screen.getByText("Operating region is required.")).toBeVisible();
    expect(screen.queryByText("Business name is required.")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Operating region"), { target: { value: "Islamabad" } });
    fireEvent.click(screen.getByRole("button", { name: "Save and continue" }));
    await waitFor(() => expect(screen.getByText("Onboarding saved.")).toBeVisible());
  });
});

describe("agent creation", () => {
  it("supports template and custom paths without asking for UUIDs", async () => {
    const createAction = vi.fn().mockResolvedValue({ state: "created" as const, agentId: agent.agent_id });
    const { container } = render(
      <AgentCreationWizard templates={templates} agentCount={0} maxAgents={2} canEdit createAction={createAction} />,
    );

    fireEvent.click(screen.getByLabelText(/Retail customer care/));
    fireEvent.change(screen.getByLabelText("Agent name"), { target: { value: "My shop assistant" } });
    fireEvent.click(screen.getByRole("button", { name: "Create agent" }));
    await waitFor(() => expect(screen.getByRole("link", { name: "Continue building" })).toBeVisible());
    expect(container.textContent).not.toContain(agent.agent_id);

    fireEvent.click(screen.getByLabelText("Start from scratch"));
    expect(screen.getByText("Custom setup")).toBeVisible();
  });

  it("blocks creation honestly when the workspace limit is reached", () => {
    render(<AgentCreationWizard templates={templates} agentCount={1} maxAgents={1} canEdit createAction={vi.fn()} />);

    expect(screen.getByText("Your workspace has reached its 1-agent limit.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Create agent" })).toBeDisabled();
  });
});

describe("revision-safe draft editor", () => {
  it("debounces autosave and reports saving then saved with the new revision", async () => {
    vi.useFakeTimers();
    const saveDraft = vi.fn().mockResolvedValue({ state: "saved" as const, agent: { ...agent, name: "Updated assistant", draft_revision: 4 } });
    render(
      <AgentDraftEditor
        initialAgent={agent}
        initialValidation={{ is_valid: false, errors: [{ code: "name", message: "Check name", field: "name" }] }}
        versions={[]}
        canEdit
        actions={{ saveDraft, validateDraft: vi.fn(), publishDraft: vi.fn(), restoreVersion: vi.fn() }}
      />,
    );

    fireEvent.change(screen.getByLabelText("Agent name"), { target: { value: "Updated assistant" } });
    expect(screen.getByRole("status", { name: "Draft save status" })).toHaveTextContent("Saving changes");
    expect(screen.getByText("Saving…")).toBeVisible();
    await act(async () => {
      vi.advanceTimersByTime(700);
      await Promise.resolve();
    });

    expect(saveDraft).toHaveBeenCalledWith(agent.agent_id, 3, expect.objectContaining({ name: "Updated assistant" }));
    const autosavePatch = saveDraft.mock.calls[0]?.[2];
    expect(autosavePatch).not.toHaveProperty("providers");
    expect(autosavePatch).not.toHaveProperty("compliance");
    expect(screen.getByText("Saved at revision 4.")).toBeVisible();
    expect(screen.queryByRole("status", { name: "Draft save status" })).not.toBeInTheDocument();
  });

  it("associates server validation with its field and explains prompt isolation", () => {
    render(
      <AgentDraftEditor
        initialAgent={agent}
        initialValidation={{ is_valid: false, errors: [{ code: "required", message: "Agent name is required.", field: "name" }] }}
        versions={[]}
        canEdit
        actions={{ saveDraft: vi.fn(), validateDraft: vi.fn(), publishDraft: vi.fn(), restoreVersion: vi.fn() }}
      />,
    );

    expect(screen.getByLabelText("Agent name")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Agent name")).toHaveAttribute("aria-describedby", "agent-name-error");
    expect(document.getElementById("agent-name-error")).toHaveTextContent("Agent name is required.");

    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    expect(screen.getByText(/Tenant data stays isolated from Wavia's core prompts/i)).toBeVisible();
  });

  it("surfaces stale conflicts and never claims the draft was saved", async () => {
    vi.useFakeTimers();
    const saveDraft = vi.fn().mockResolvedValue({ state: "conflict" as const, message: "A newer draft exists." });
    render(
      <AgentDraftEditor
        initialAgent={agent}
        initialValidation={{ is_valid: true, errors: [] }}
        versions={[]}
        canEdit
        actions={{ saveDraft, validateDraft: vi.fn(), publishDraft: vi.fn(), restoreVersion: vi.fn() }}
      />,
    );

    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Changed elsewhere" } });
    await act(async () => {
      vi.advanceTimersByTime(700);
      await Promise.resolve();
    });

    expect(screen.getByRole("alert")).toHaveTextContent("A newer draft exists.");
    expect(screen.queryByText(/Saved at revision/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload latest draft" })).toBeVisible();
  });

  it("stops automatic retries after a save error until the user edits again", async () => {
    vi.useFakeTimers();
    const saveDraft = vi.fn().mockResolvedValue({ state: "error" as const, message: "Saving is temporarily unavailable." });
    render(
      <AgentDraftEditor
        initialAgent={agent}
        initialValidation={{ is_valid: true, errors: [] }}
        versions={[]}
        canEdit
        actions={{ saveDraft, validateDraft: vi.fn(), publishDraft: vi.fn(), restoreVersion: vi.fn() }}
      />,
    );

    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "One attempted save" } });
    await act(async () => {
      vi.advanceTimersByTime(700);
      await Promise.resolve();
    });
    expect(screen.getByRole("alert")).toHaveTextContent("Saving is temporarily unavailable.");
    await act(async () => vi.advanceTimersByTime(1_400));
    expect(saveDraft).toHaveBeenCalledTimes(1);
  });

  it("uses API validation as the publish gate and restores immutable versions to a new draft", async () => {
    const validateDraft = vi.fn().mockResolvedValue({ is_valid: true, errors: [] });
    const publishDraft = vi.fn().mockResolvedValue({ state: "published" as const, version: 2, agent: { ...agent, version: 2, draft_revision: 4, is_published: true } });
    const restoreVersion = vi.fn().mockResolvedValue({ state: "restored" as const, agent: { ...agent, name: "Version one", draft_revision: 5 } });
    render(
      <AgentDraftEditor
        initialAgent={agent}
        initialValidation={{ is_valid: false, errors: [{ code: "required", message: "Complete setup", field: "name" }] }}
        versions={[{ version: 1, published_by: "user", published_at: "2026-10-30T00:00:00Z" }]}
        canEdit
        actions={{ saveDraft: vi.fn(), validateDraft, publishDraft, restoreVersion }}
      />,
    );

    expect(screen.getByRole("button", { name: "Publish agent" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Check readiness" }));
    await waitFor(() => expect(screen.getByText("Ready to publish.")).toBeVisible());
    expect(screen.getByRole("button", { name: "Publish agent" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Publish agent" }));
    await waitFor(() => expect(screen.getByText("Published version 2.")).toBeVisible());

    fireEvent.click(screen.getByRole("button", { name: "Restore version 1" }));
    await waitFor(() => expect(screen.getByDisplayValue("Version one")).toBeVisible());
    expect(screen.getByText("Version 1 remains immutable; its snapshot was copied into a new draft.")).toBeVisible();
  });

  it("renders a viewer-safe read-only state and keeps advanced controls disclosed", () => {
    const { container } = render(
      <AgentDraftEditor
        initialAgent={agent}
        initialValidation={{ is_valid: true, errors: [] }}
        versions={[]}
        canEdit={false}
        actions={{ saveDraft: vi.fn(), validateDraft: vi.fn(), publishDraft: vi.fn(), restoreVersion: vi.fn() }}
      />,
    );

    expect(screen.getByText("You have view-only access.")).toBeVisible();
    expect(screen.getByLabelText("Agent name")).toBeDisabled();
    expect(screen.queryByLabelText("System prompt")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Advanced"));
    expect(screen.getByLabelText("System prompt")).toBeDisabled();
    expect(container.textContent).not.toContain(agent.agent_id);
  });
});
