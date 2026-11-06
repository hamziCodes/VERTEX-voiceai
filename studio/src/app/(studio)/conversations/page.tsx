import { z } from "zod";

import { requireWorkspace } from "@/auth/workspace";
import { ConversationListView } from "@/features/conversations/conversation-list-view";
import { listConversations } from "@/features/conversations/data";
import { OperationsNavigation } from "@/features/operations/operations-navigation";

export default async function ConversationsPage({ searchParams }: { searchParams: Promise<{ cursor?: string }> }) {
  const { cursor: rawCursor } = await searchParams;
  const cursor = z.string().max(1024).safeParse(rawCursor).data;
  const { session, membership } = await requireWorkspace("conversation:read");
  const page = await listConversations(session, membership.tenant_id, cursor);

  return (
    <>
      <OperationsNavigation role={membership.role} />
      <ConversationListView page={page} />
    </>
  );
}
