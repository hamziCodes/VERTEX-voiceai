import "server-only";

import type { StudioServerSession } from "@/data/dto";
import { controlPlaneRequest } from "@/data/control-plane";
import {
  agentListSchema,
  agentSchema,
  agentVersionsSchema,
  entitlementsSchema,
  templateResponseSchema,
  validationResultSchema,
} from "@/data/schema";

import type { AgentTemplateDto } from "./types";

export function loadAgents(session: StudioServerSession, tenantId: string) {
  return controlPlaneRequest("/v1/agents", { schema: agentListSchema, session, selectedTenantId: tenantId });
}

export function loadEntitlements(session: StudioServerSession, tenantId: string) {
  return controlPlaneRequest("/v1/entitlements", { schema: entitlementsSchema, session, selectedTenantId: tenantId });
}

export async function loadTemplates(session: StudioServerSession, tenantId: string): Promise<AgentTemplateDto[]> {
  const response = await controlPlaneRequest("/v1/agents/templates", { schema: templateResponseSchema, session, selectedTenantId: tenantId });
  return response.templates.map(({ template_id, config }) => ({ template_id, ...config }));
}

export function loadAgent(session: StudioServerSession, tenantId: string, agentId: string) {
  return controlPlaneRequest(`/v1/agents/${agentId}`, { schema: agentSchema, session, selectedTenantId: tenantId });
}

export function loadAgentValidation(session: StudioServerSession, tenantId: string, agentId: string) {
  return controlPlaneRequest(`/v1/agents/${agentId}/validate`, { method: "POST", schema: validationResultSchema, session, selectedTenantId: tenantId });
}

export function loadAgentVersions(session: StudioServerSession, tenantId: string, agentId: string) {
  return controlPlaneRequest(`/v1/agents/${agentId}/versions`, { schema: agentVersionsSchema, session, selectedTenantId: tenantId });
}
