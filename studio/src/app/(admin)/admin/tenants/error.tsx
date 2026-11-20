"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function TenantsError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="Nothing was changed. Try loading the tenant directory again."
      title="Tenant directory unavailable"
      tone="error"
    />
  );
}
