export default function AgentsLoading() {
  return (
    <section aria-busy="true" aria-label="Loading agents" className="directory-page">
      <div className="skeleton skeleton--title" />
      <div className="skeleton skeleton--summary" />
      <div className="directory-panel skeleton-table">
        <div className="skeleton skeleton--toolbar" />
        <div className="skeleton skeleton--row" />
        <div className="skeleton skeleton--row" />
        <div className="skeleton skeleton--row" />
      </div>
      <span className="sr-only">Loading agents…</span>
    </section>
  );
}
