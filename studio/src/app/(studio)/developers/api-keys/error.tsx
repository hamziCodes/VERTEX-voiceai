"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function ApiKeysError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="No key was created or revoked. Try loading API keys again."
      title="API keys unavailable"
      tone="error"
    />
  );
}
