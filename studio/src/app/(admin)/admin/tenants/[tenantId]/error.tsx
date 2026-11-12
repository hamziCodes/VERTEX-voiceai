"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function TenantDetailError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="Nothing was changed. Try loading this tenant summary again."
      title="Tenant summary unavailable"
      tone="error"
    />
  );
}
