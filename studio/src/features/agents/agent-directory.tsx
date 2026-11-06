"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { AgentDto } from "./types";

type StatusFilter = "all" | "published" | "draft";
type SortOrder = "name-asc" | "name-desc" | "version-desc";

export function AgentDirectory({
  agents,
  canCreate,
  canEdit,
  maxAgents,
}: {
  agents: AgentDto[];
  canCreate: boolean;
  canEdit: boolean;
  maxAgents: number;
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [sort, setSort] = useState<SortOrder>("name-asc");

  const visibleAgents = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return agents
      .filter((agent) => status === "all" || (status === "published" ? agent.is_published : !agent.is_published))
      .filter((agent) => {
        if (!normalized) return true;
        return [agent.name, agent.description, ...agent.languages].some((value) => value.toLocaleLowerCase().includes(normalized));
      })
      .toSorted((left, right) => {
        if (sort === "version-desc") return right.version - left.version || left.name.localeCompare(right.name);
        const direction = sort === "name-desc" ? -1 : 1;
        return left.name.localeCompare(right.name) * direction;
      });
  }, [agents, query, sort, status]);

  function clearFilters() {
    setQuery("");
    setStatus("all");
    setSort("name-asc");
  }

  return (
    <section aria-labelledby="agent-directory-title" className="directory-page">
      <header className="screen-header">
        <div>
          <p className="screen-eyebrow">Build</p>
          <h1 id="agent-directory-title">Agents</h1>
          <p className="screen-summary">Manage each agent&apos;s draft, published version and browser test entry point.</p>
        </div>
        {canCreate && agents.length > 0 ? <Link className="button button--primary" href="/agents/new">Create agent</Link> : null}
      </header>

      <div className="directory-meta">
        <strong>{agents.length} of {maxAgents}</strong>
        <span>agent slots used</span>
      </div>

      {agents.length === 0 ? (
        <div className="empty-state">
          <span aria-hidden="true" className="empty-state__mark">A</span>
          <h2>No agents yet</h2>
          <p>Start from a guided template or a blank setup.</p>
          {canCreate ? <Link className="button button--primary" href="/agents/new">Create agent</Link> : null}
        </div>
      ) : (
        <div className="directory-panel">
          <div className="directory-toolbar">
            <label className="search-field">
              <span className="sr-only">Search agents</span>
              <input onChange={(event) => setQuery(event.target.value)} placeholder="Search agents" type="search" value={query} />
            </label>
            <label className="compact-field">
              <span>Status</span>
              <select onChange={(event) => setStatus(event.target.value as StatusFilter)} value={status}>
                <option value="all">All statuses</option>
                <option value="published">Published</option>
                <option value="draft">Drafts</option>
              </select>
            </label>
            <label className="compact-field">
              <span>Sort</span>
              <select onChange={(event) => setSort(event.target.value as SortOrder)} value={sort}>
                <option value="name-asc">Name A-Z</option>
                <option value="name-desc">Name Z-A</option>
                <option value="version-desc">Newest version</option>
              </select>
            </label>
          </div>

          {visibleAgents.length === 0 ? (
            <div className="empty-state empty-state--compact">
              <h2>No agents match these filters.</h2>
              <p>Change the search or status filter to see your agents.</p>
              <button className="button button--secondary" onClick={clearFilters} type="button">Clear filters</button>
            </div>
          ) : (
            <table className="agent-table">
              <caption className="sr-only">Agents in this workspace</caption>
              <thead>
                <tr><th scope="col">Agent</th><th scope="col">Languages</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th></tr>
              </thead>
              <tbody>
                {visibleAgents.map((agent) => (
                  <tr key={agent.agent_id}>
                    <td data-label="Agent">
                      <strong className="agent-table__name">{agent.name}</strong>
                      <span className="agent-table__description">{agent.description || "No description yet."}</span>
                    </td>
                    <td data-label="Languages"><span className="technical-value">{agent.languages.join(", ") || "Not set"}</span></td>
                    <td data-label="Status">
                      <span className={`status-pill ${agent.is_published ? "status-pill--success" : "status-pill--warning"}`}>
                        <span aria-hidden="true" className="status-pill__dot" />
                        {agent.is_published ? `Published · v${agent.version}` : "Draft"}
                      </span>
                    </td>
                    <td data-label="Actions">
                      <div className="row-actions">
                        <Link className="button button--secondary" href={`/agents/${agent.agent_id}/build`}>{canEdit ? "Open builder" : "View agent"}</Link>
                        {agent.is_published ? <Link className="text-action" href={`/agents/${agent.agent_id}/test`}>Test voice</Link> : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}
