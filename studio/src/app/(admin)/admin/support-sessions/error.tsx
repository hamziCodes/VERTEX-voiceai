"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function SupportSessionsError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="No session was started or ended. Try loading support sessions again."
      title="Support sessions unavailable"
      tone="error"
    />
  );
}
