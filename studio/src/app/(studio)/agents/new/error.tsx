"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function NewAgentError({ reset }: { reset: () => void }) {
  return <StatePanel actions={<button className="button button--primary" onClick={reset} type="button">Try again</button>} description="No agent was created. No private error details were shown." title="Agent creation unavailable" tone="error" />;
}
