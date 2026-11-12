"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function ConversationDetailError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="Nothing was changed. Try loading this conversation again."
      title="Conversation unavailable"
      tone="error"
    />
  );
}
