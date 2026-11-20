"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function ApiKeysError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="No endpoint was created or disabled. Try loading webhooks again."
      title="Webhooks unavailable"
      tone="error"
    />
  );
}
