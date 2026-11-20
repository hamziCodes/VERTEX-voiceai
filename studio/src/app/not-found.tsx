import Link from "next/link";

import { StatePanel } from "@/components/studio/state-panel";

export default function NotFoundPage() {
  return (
    <main className="entry-shell">
      <div className="fallback-wrap">
        <div className="entry-wordmark"><span aria-hidden="true">W</span> Wavia Studio</div>
        <StatePanel
          actions={<Link className="button button--primary" href="/">Return to Studio</Link>}
          description="The Studio page you requested does not exist or is no longer available."
          title="Page not found"
        />
      </div>
    </main>
  );
}
