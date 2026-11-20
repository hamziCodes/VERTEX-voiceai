"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function SupportSessionError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="No tenant data was changed. Try loading this support session again."
      title="Support session unavailable"
      tone="error"
    />
  );
}
