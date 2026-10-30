"use client";

export default function StudioError({ reset }: { reset: () => void }) {
  return (
    <main>
      <h1>Studio could not load</h1>
      <p>No private error details were shown. Try the request again.</p>
      <button type="button" onClick={reset}>
        Try again
      </button>
    </main>
  );
}
