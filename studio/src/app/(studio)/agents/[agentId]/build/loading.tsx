export default function PersonaLoading() {
  return (
    <section aria-busy="true" aria-label="Loading persona editor">
      <div className="skeleton skeleton--tabs" />
      <div className="skeleton skeleton--title" />
      <div className="skeleton skeleton--summary" />
      <div className="persona-layout">
        <div className="skeleton skeleton--form" />
        <div className="skeleton skeleton--side" />
      </div>
      <span className="sr-only">Loading persona editor…</span>
    </section>
  );
}
