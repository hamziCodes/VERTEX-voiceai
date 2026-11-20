import Link from "next/link";
import { redirect } from "next/navigation";
import { z } from "zod";

import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { PageHeader } from "@/components/studio/page-header";
import { ControlPlaneError } from "@/data/control-plane";
import { ConversationDetailView } from "@/features/conversations/conversation-detail-view";
import { getConversation, getConversationIntelligence } from "@/features/conversations/data";
import { transportLabel } from "@/features/operations/labels";
import { OperationsNavigation } from "@/features/operations/operations-navigation";
import { decideReviewAction } from "@/features/webhooks/actions";
import { formatDateTime } from "@/lib/format";

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
    <section className="operate-page">
      <Link className="text-action operate-back" href="/conversations">← Conversation history</Link>
      <PageHeader
        eyebrow="Operate"
        summary={`Started ${formatDateTime(conversation.started_at)} · ${transportLabel(conversation.transport_type)}`}
        title="Conversation detail"
      />
      <OperationsNavigation capabilities={membership.capabilities} />
      <ConversationDetailView
        conversation={conversation}
        intelligence={intelligence}
        reviewAction={hasWorkspaceCapability(membership.capabilities, "extraction:write") ? decideReviewAction : undefined}
      />
    </section>
  );
}
