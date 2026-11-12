"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function AdminOverviewError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="Nothing was changed. Try loading the internal overview again."
      title="Internal area unavailable"
      tone="error"
    />
  );
}
