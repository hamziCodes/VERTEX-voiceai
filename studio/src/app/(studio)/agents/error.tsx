"use client";

export default function AgentsError({ reset }: { reset: () => void }) {
  return (
    <section className="state-panel" role="alert">
      <p className="screen-eyebrow">Agents unavailable</p>
      <h1>We could not load your agents</h1>
      <p>No private error details were shown. Try the request again.</p>
      <button className="button button--primary" onClick={reset} type="button">Try again</button>
    </section>
  );
}
