import "server-only";

import type { StudioServerSession } from "@/data/dto";
import { controlPlaneRequest } from "@/data/control-plane";
import { agentListSchema, entitlementsSchema, knowledgeBaseListSchema, knowledgeSourceListSchema } from "@/data/schema";

export function loadKnowledgeBases(session: StudioServerSession, tenantId: string) {
  return controlPlaneRequest("/v1/knowledge-bases", { schema: knowledgeBaseListSchema, session, selectedTenantId: tenantId });
}

export function loadKnowledgeSources(session: StudioServerSession, tenantId: string, knowledgeBaseId: string) {
  return controlPlaneRequest(`/v1/knowledge-bases/${knowledgeBaseId}/sources`, { schema: knowledgeSourceListSchema, session, selectedTenantId: tenantId });
}

export function loadKnowledgeAgents(session: StudioServerSession, tenantId: string) {
  return controlPlaneRequest("/v1/agents", { schema: agentListSchema, session, selectedTenantId: tenantId });
}

export function loadKnowledgeEntitlements(session: StudioServerSession, tenantId: string) {
  return controlPlaneRequest("/v1/entitlements", { schema: entitlementsSchema, session, selectedTenantId: tenantId });
}
