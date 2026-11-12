"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function PlatformAuditError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="Nothing was changed. Try loading the platform audit again."
      title="Platform audit unavailable"
      tone="error"
    />
  );
}
