"use client";

import { StatePanel } from "@/components/studio/state-panel";

export default function StudioError({ reset }: { reset: () => void }) {
  return (
    <main className="entry-shell">
      <div className="fallback-wrap">
        <div className="entry-wordmark"><span aria-hidden="true">W</span> Wavia Studio</div>
        <StatePanel
          actions={<button className="button button--primary" type="button" onClick={reset}>Try again</button>}
          description="No private error details were shown. Try the request again."
          title="Studio could not load"
          tone="error"
        />
      </div>
    </main>
  );
}
