"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function StaffError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="No staff role was changed. Try loading platform staff again."
      title="Staff unavailable"
      tone="error"
    />
  );
}
