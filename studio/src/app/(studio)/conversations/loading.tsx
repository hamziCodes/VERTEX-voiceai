import { StatePanel } from "@/components/studio/state-panel";

export default function ConversationsLoading() {
  return <StatePanel description="Checking recorded conversations for this workspace." title="Loading conversations" tone="loading" />;
}
