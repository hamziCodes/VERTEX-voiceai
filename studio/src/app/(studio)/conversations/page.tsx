import { z } from "zod";

import { requireWorkspace } from "@/auth/workspace";
import { PageHeader } from "@/components/studio/page-header";
import { ConversationListView } from "@/features/conversations/conversation-list-view";
import { listConversations } from "@/features/conversations/data";
import { OperationsNavigation } from "@/features/operations/operations-navigation";

export default async function ConversationsPage({ searchParams }: { searchParams: Promise<{ cursor?: string }> }) {
  const { cursor: rawCursor } = await searchParams;
  const cursor = z.string().max(1024).safeParse(rawCursor).data;
  const { session, membership } = await requireWorkspace("conversation:read");
  const page = await listConversations(session, membership.tenant_id, cursor);

  return (
    <section className="operate-page">
      <PageHeader
        eyebrow="Operate"
        summary="Review recorded web and phone conversations, their transcripts and post-call results for this workspace."
        title="Conversation history"
      />
      <OperationsNavigation capabilities={membership.capabilities} />
      <ConversationListView page={page} />
    </section>
  );
}
