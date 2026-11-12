"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function OperationsError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="The health snapshot could not be loaded. Nothing was changed."
      title="Operations unavailable"
      tone="error"
    />
  );
}
