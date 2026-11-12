"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function KnowledgeError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="No knowledge was changed. Try loading this workspace's knowledge again."
      title="Knowledge unavailable"
      tone="error"
    />
  );
}
