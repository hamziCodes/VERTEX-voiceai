import { redirect } from "next/navigation";
import { z } from "zod";

import { requireWorkspace } from "@/auth/workspace";
import { ControlPlaneError } from "@/data/control-plane";
import { ConversationDetailView } from "@/features/conversations/conversation-detail-view";
import { getConversation, getConversationIntelligence } from "@/features/conversations/data";
import { OperationsNavigation } from "@/features/operations/operations-navigation";

async function loadConversationDetail(
  session: Parameters<typeof getConversation>[0],
  tenantId: string,
  callId: string,
) {
  try {
    return await Promise.all([
      getConversation(session, tenantId, callId),
      getConversationIntelligence(session, tenantId, callId),
    ]);
  } catch (error) {
    if (error instanceof ControlPlaneError && error.status === 404) redirect("/conversations");
    throw error;
  }
}

export default async function ConversationDetailPage({ params }: { params: Promise<{ callId: string }> }) {
  const { callId } = await params;
  if (!z.string().uuid().safeParse(callId).success) redirect("/conversations");
  const { session, membership } = await requireWorkspace("conversation:read");

  const [conversation, intelligence] = await loadConversationDetail(session, membership.tenant_id, callId);
  return (
    <>
      <OperationsNavigation capabilities={membership.capabilities} />
      <ConversationDetailView conversation={conversation} intelligence={intelligence} />
    </>
  );
}
