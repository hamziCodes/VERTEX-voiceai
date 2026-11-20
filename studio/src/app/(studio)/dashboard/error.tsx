"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function DashboardError({ reset }: { reset: () => void }) {
  return <StatePanel actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>} description="No private error details were shown. Try loading the workspace overview again." title="Workspace overview unavailable" tone="error" />;
}
