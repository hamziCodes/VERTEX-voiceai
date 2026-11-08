"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function TestError({ reset }: { reset: () => void }) {
  return <StatePanel actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>} description="No voice session was started. Try loading agent readiness again." title="Test readiness unavailable" tone="error" />;
}
