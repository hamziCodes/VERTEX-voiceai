"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function MembersError({ reset }: { reset: () => void }) {
  return (
    <StatePanel
      actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>}
      description="No membership was changed. Try loading the member list again."
      title="Members unavailable"
      tone="error"
    />
  );
}
