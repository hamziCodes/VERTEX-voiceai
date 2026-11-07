"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function OnboardingError({ reset }: { reset: () => void }) {
  return <StatePanel actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>} description="No private error details were shown. Your saved setup was not changed." title="Workspace setup unavailable" tone="error" />;
}
