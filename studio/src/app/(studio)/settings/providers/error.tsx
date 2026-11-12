"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function ProvidersError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="No credential was stored or revoked. Try loading provider credentials again."
      title="Provider credentials unavailable"
      tone="error"
    />
  );
}
