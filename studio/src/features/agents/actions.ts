"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { requireWorkspace } from "@/auth/workspace";
import { ControlPlaneError, controlPlaneRequest } from "@/data/control-plane";
import { agentSchema, autosaveResponseSchema, publishResponseSchema, validationResultSchema } from "@/data/schema";

import { loadAgents, loadEntitlements, loadTemplates } from "./data";
import type { AgentDto, PublishDraftResult, RestoreVersionResult, SaveDraftResult, ValidationResultDto } from "./types";

const agentIdSchema = z.string().uuid();

function safeId(value: string): string {
  return agentIdSchema.parse(value);
}

function failure(error: unknown): { state: "conflict" | "error"; message: string } {
  if (error instanceof ControlPlaneError) {
    return { state: error.status === 409 ? "conflict" : "error", message: error.message };
  }
  return { state: "error", message: "The action could not be completed." };
}

export async function createAgentAction(input: { mode: "template" | "custom"; templateId?: string; name: string }): Promise<{ state: "created"; agentId: string } | { state: "error"; message: string }> {
  const { session, membership } = await requireWorkspace("agent:write");
  try {
    const name = input.name.trim();
    if (!name) return { state: "error", message: "Enter an agent name." };
    const [agents, entitlements] = await Promise.all([
      loadAgents(session, membership.tenant_id),
      loadEntitlements(session, membership.tenant_id),
    ]);
    if (agents.length >= entitlements.max_agents) return { state: "error", message: "Your workspace has reached its agent limit." };

    let body: Record<string, unknown> = { name };
    if (input.mode === "template") {
      const templates = await loadTemplates(session, membership.tenant_id);
      const template = templates.find((item) => item.template_id === input.templateId);
      if (!template) return { state: "error", message: "Choose a valid starting template." };
      body = {
        name,
        description: template.description,
        persona: template.persona,
        languages: template.languages,
        providers: template.providers,
        compliance: template.compliance,
      };
    }
    const agent = await controlPlaneRequest("/v1/agents", {
      method: "POST",
      json: body,
      schema: agentSchema,
      session,
      selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/agents");
    return { state: "created", agentId: agent.agent_id };
  } catch (error) {
    return { state: "error", message: failure(error).message };
  }
}

export async function saveAgentDraftAction(agentId: string, expectedRevision: number, patch: Partial<AgentDto>): Promise<SaveDraftResult> {
  const { session, membership } = await requireWorkspace("agent:write");
  try {
    const response = await controlPlaneRequest(`/v1/agents/${safeId(agentId)}/autosave`, {
      method: "PATCH",
      json: { patch, expected_revision: expectedRevision, debounce_seconds: 0, force: true },
      schema: autosaveResponseSchema,
      session,
      selectedTenantId: membership.tenant_id,
    });
    revalidatePath(`/agents/${agentId}/build`);
    return { state: "saved", agent: response.agent };
  } catch (error) {
    return failure(error);
  }
}

export async function validateAgentDraftAction(agentId: string): Promise<ValidationResultDto> {
  const { session, membership } = await requireWorkspace("agent:read");
  try {
    return await controlPlaneRequest(`/v1/agents/${safeId(agentId)}/validate`, {
      method: "POST", schema: validationResultSchema, session, selectedTenantId: membership.tenant_id,
    });
  } catch {
    return { is_valid: false, errors: [{ code: "validation_unavailable", message: "Readiness could not be checked.", field: null }] };
  }
}

export async function publishAgentDraftAction(agentId: string, expectedRevision: number): Promise<PublishDraftResult> {
  const { session, membership } = await requireWorkspace("agent:write");
  try {
    const response = await controlPlaneRequest(`/v1/agents/${safeId(agentId)}/publish`, {
      method: "POST", json: { expected_revision: expectedRevision }, schema: publishResponseSchema, session, selectedTenantId: membership.tenant_id,
    });
    revalidatePath(`/agents/${agentId}/build`);
    return { state: "published", version: response.version, agent: response.config };
  } catch (error) {
    return failure(error);
  }
}

export async function restoreAgentVersionAction(agentId: string, version: number, expectedRevision: number): Promise<RestoreVersionResult> {
  const { session, membership } = await requireWorkspace("agent:write");
  try {
    const agent = await controlPlaneRequest(`/v1/agents/${safeId(agentId)}/versions/${version}/restore`, {
      method: "POST", json: { expected_revision: expectedRevision }, schema: agentSchema, session, selectedTenantId: membership.tenant_id,
    });
    revalidatePath(`/agents/${agentId}/build`);
    return { state: "restored", agent };
  } catch (error) {
    return failure(error);
  }
}
