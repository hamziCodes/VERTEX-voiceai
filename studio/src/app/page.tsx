import Link from "next/link";

export default function StudioHomePage() {
  return (
    <main className="entry-shell">
      <section className="entry-panel entry-panel--welcome">
        <div className="entry-wordmark"><span aria-hidden="true">W</span> Wavia Studio</div>
        <div className="entry-panel__content">
          <p className="screen-eyebrow">Voice agent workspace</p>
          <h1>Build and operate your voice agents</h1>
          <p className="entry-lede">Configure agents, test conversations, connect channels, and review operations from one secure workspace.</p>
          <Link className="button button--primary" href="/sign-in">Sign in to Studio</Link>
        </div>
        <p className="entry-footnote">Access is controlled by your workspace membership.</p>
      </section>
    </main>
  );
}
