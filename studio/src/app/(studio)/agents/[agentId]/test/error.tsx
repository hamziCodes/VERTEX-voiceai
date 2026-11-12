"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function AgentTestError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="No voice session was started. Try loading the test sandbox again."
      title="Voice test unavailable"
      tone="error"
    />
  );
}
