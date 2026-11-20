"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { requireWorkspace } from "@/auth/workspace";
import { ControlPlaneError, controlPlaneRequest } from "@/data/control-plane";
import { knowledgeBaseSchema, knowledgeBindingSchema, knowledgePreviewSchema, knowledgeRetrySchema, knowledgeSourceSchema } from "@/data/schema";

import type { KnowledgeActionError, KnowledgeActions } from "./types";

const idSchema = z.string().uuid();

function safeId(value: string): string {
  return idSchema.parse(value);
}

function failure(error: unknown): KnowledgeActionError {
  return { state: "error", message: error instanceof ControlPlaneError ? error.message : "The action could not be completed." };
}

export const createKnowledgeBaseAction: KnowledgeActions["createBase"] = async (name) => {
  const { session, membership } = await requireWorkspace("knowledge:write");
  try {
    const knowledgeBase = await controlPlaneRequest("/v1/knowledge-bases", {
      method: "POST", json: { name: name.trim() }, schema: knowledgeBaseSchema, session, selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/knowledge");
    return { state: "created", knowledgeBase };
  } catch (error) { return failure(error); }
};

export const uploadKnowledgeSourceAction: KnowledgeActions["uploadSource"] = async (knowledgeBaseId, file) => {
  const { session, membership } = await requireWorkspace("knowledge:write");
  try {
    const body = new FormData();
    body.set("source", file);
    const source = await controlPlaneRequest(`/v1/knowledge-bases/${safeId(knowledgeBaseId)}/sources`, {
      method: "POST", body, schema: knowledgeSourceSchema, session, selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/knowledge");
    return { state: "uploaded", source };
  } catch (error) { return failure(error); }
};

export const addKnowledgeFaqAction: KnowledgeActions["addFaq"] = async (knowledgeBaseId, input) => {
  const { session, membership } = await requireWorkspace("knowledge:write");
  try {
    const source = await controlPlaneRequest(`/v1/knowledge-bases/${safeId(knowledgeBaseId)}/faqs`, {
      method: "POST", json: { name: input.name, items: [{ question: input.question, answer: input.answer }] }, schema: knowledgeSourceSchema, session, selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/knowledge");
    return { state: "uploaded", source };
  } catch (error) { return failure(error); }
};

export const deleteKnowledgeSourceAction: KnowledgeActions["deleteSource"] = async (knowledgeBaseId, sourceId) => {
  const { session, membership } = await requireWorkspace("knowledge:write");
  try {
    await controlPlaneRequest(`/v1/knowledge-bases/${safeId(knowledgeBaseId)}/sources/${safeId(sourceId)}`, {
      method: "DELETE", schema: z.null(), session, selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/knowledge");
    return { state: "deleted" };
  } catch (error) { return failure(error); }
};

export const retryKnowledgeSourceAction: KnowledgeActions["retrySource"] = async (knowledgeBaseId, sourceId) => {
  const { session, membership } = await requireWorkspace("knowledge:write");
  try {
    const result = await controlPlaneRequest(`/v1/knowledge-bases/${safeId(knowledgeBaseId)}/sources/${safeId(sourceId)}/retry`, {
      method: "POST", schema: knowledgeRetrySchema, session, selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/knowledge");
    return { state: "queued", sourceId: result.source_id };
  } catch (error) { return failure(error); }
};

export const previewKnowledgeAction: KnowledgeActions["preview"] = async (knowledgeBaseId, query) => {
  const { session, membership } = await requireWorkspace("knowledge:read");
  try {
    const result = await controlPlaneRequest(`/v1/knowledge-bases/${safeId(knowledgeBaseId)}/preview-query`, {
      method: "POST", json: { query: query.trim(), top_k: 4 }, schema: knowledgePreviewSchema, session, selectedTenantId: membership.tenant_id,
    });
    return { state: "complete", results: result.results };
  } catch (error) { return failure(error); }
};

export const activateKnowledgeBaseAction: KnowledgeActions["activate"] = async (knowledgeBaseId) => {
  const { session, membership } = await requireWorkspace("knowledge:write");
  try {
    const knowledgeBase = await controlPlaneRequest(`/v1/knowledge-bases/${safeId(knowledgeBaseId)}/activate`, {
      method: "POST", schema: knowledgeBaseSchema, session, selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/knowledge");
    return { state: "active", knowledgeBase };
  } catch (error) { return failure(error); }
};

export const bindKnowledgeToAgentAction: KnowledgeActions["bindAgent"] = async (knowledgeBaseId, agentId) => {
  const { session, membership } = await requireWorkspace("knowledge:write");
  try {
    const binding = await controlPlaneRequest(`/v1/knowledge-bases/${safeId(knowledgeBaseId)}/bind/${safeId(agentId)}`, {
      method: "POST", schema: knowledgeBindingSchema, session, selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/knowledge");
    revalidatePath(`/agents/${agentId}/build`);
    return { state: "bound", agentVersion: binding.agent_config_version, knowledgeRevision: binding.knowledge_revision };
  } catch (error) { return failure(error); }
};
