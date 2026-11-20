"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function WebChannelError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="Nothing was changed. Try loading the web integration again."
      title="Web channel unavailable"
      tone="error"
    />
  );
}
