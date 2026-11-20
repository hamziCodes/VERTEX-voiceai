import "server-only";

import type { StudioServerSession } from "@/data/dto";
import { controlPlaneRequest } from "@/data/control-plane";
import { conversationDetailSchema, conversationIntelligenceSchema, conversationPageSchema } from "@/data/schema";

export function listConversations(session: StudioServerSession, tenantId: string, cursor?: string) {
  const query = new URLSearchParams({ limit: "25" });
  if (cursor) query.set("cursor", cursor);
  return controlPlaneRequest(`/v1/conversations?${query.toString()}`, {
    schema: conversationPageSchema,
    session,
    selectedTenantId: tenantId,
  });
}

export function getConversation(session: StudioServerSession, tenantId: string, callId: string) {
  return controlPlaneRequest(`/v1/conversations/${callId}`, {
    schema: conversationDetailSchema,
    session,
    selectedTenantId: tenantId,
  });
}

export function getConversationIntelligence(session: StudioServerSession, tenantId: string, callId: string) {
  return controlPlaneRequest(`/v1/conversations/${callId}/intelligence`, {
    schema: conversationIntelligenceSchema,
    session,
    selectedTenantId: tenantId,
  });
}
