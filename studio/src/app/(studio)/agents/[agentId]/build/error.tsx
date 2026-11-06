"use client";

export default function PersonaError({ reset }: { reset: () => void }) {
  return (
    <section className="state-panel" role="alert">
      <p className="screen-eyebrow">Persona unavailable</p>
      <h1>We could not load this agent</h1>
      <p>No private error details were shown. Try the request again.</p>
      <button className="button button--primary" onClick={reset} type="button">Try again</button>
    </section>
  );
}
