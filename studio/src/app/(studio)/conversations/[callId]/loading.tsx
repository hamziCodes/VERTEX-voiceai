import { StatePanel } from "@/components/studio/state-panel";

export default function ConversationDetailLoading() {
  return <StatePanel description="Checking the transcript, recording state and post-call results." title="Loading conversation" tone="loading" />;
}
