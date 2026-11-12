"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function TelephonyError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="No calling policy was changed and no call was placed. Try loading telephony again."
      title="Telephony unavailable"
      tone="error"
    />
  );
}
