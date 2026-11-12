"use client";

import Link from "next/link";
import { useState } from "react";

import { StatusBadge } from "@/components/studio/status-badge";
import { formatDateTime } from "@/lib/format";
import { dispositionTone, humanize, transportLabel } from "@/features/operations/labels";

import type { ConversationPageDto } from "./types";

export function ConversationListView({ page }: { page: ConversationPageDto }) {
  const [transport, setTransport] = useState("all");
  const [disposition, setDisposition] = useState("all");
  const visible = page.items.filter((item) =>
    (transport === "all" || item.transport_type === transport)
    && (disposition === "all" || item.disposition === disposition)
  );

  if (page.items.length === 0) {
    return (
      <section aria-labelledby="conversation-list-heading" className="form-panel operate-panel">
        <h2 className="operate-panel__title" id="conversation-list-heading">Recorded conversations</h2>
        <p className="muted-copy">No conversations have been recorded for this workspace.</p>
      </section>
    );
  }

  const transports = [...new Set(page.items.map((item) => item.transport_type))];
  const dispositions = [...new Set(page.items.map((item) => item.disposition))];

  return (
    <section aria-labelledby="conversation-list-heading" className="form-panel operate-panel">
      <h2 className="operate-panel__title" id="conversation-list-heading">Recorded conversations</h2>
      <div className="operate-filters">
        <div className="compact-field">
          <label htmlFor="conversation-transport">Transport</label>
          <select id="conversation-transport" onChange={(event) => setTransport(event.target.value)} value={transport}>
            <option value="all">All</option>
            {transports.map((value) => <option key={value} value={value}>{transportLabel(value)}</option>)}
          </select>
        </div>
        <div className="compact-field">
          <label htmlFor="conversation-disposition">Disposition</label>
          <select id="conversation-disposition" onChange={(event) => setDisposition(event.target.value)} value={disposition}>
            <option value="all">All</option>
            {dispositions.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
          </select>
        </div>
        <p className="field-help operate-filters__note">Filters apply to this loaded page. Use pagination to inspect additional records.</p>
      </div>

      {visible.length === 0 ? (
        <p className="muted-copy operate-empty">No conversations on this page match the selected filters.</p>
      ) : (
        <table aria-label="Conversations" className="data-table">
          <thead>
            <tr>
              <th scope="col">Started</th>
              <th scope="col">Transport</th>
              <th scope="col">Disposition</th>
              <th scope="col">Turns</th>
              <th scope="col">Recording</th>
              <th scope="col"><span className="sr-only">Open</span></th>
            </tr>
          </thead>
          <tbody>
            {visible.map((item) => (
              <tr key={item.call_id}>
                <td data-label="Started"><span className="technical-value">{formatDateTime(item.started_at)}</span></td>
                <td data-label="Transport">{transportLabel(item.transport_type)}</td>
                <td data-label="Disposition"><StatusBadge tone={dispositionTone(item.disposition)}>{humanize(item.disposition)}</StatusBadge></td>
                <td data-label="Turns"><span className="technical-value">{item.turn_count}</span></td>
                <td data-label="Recording">{humanize(item.recording_state)}</td>
                <td className="data-table__actions" data-label="Open">
                  <Link className="text-action" href={`/conversations/${encodeURIComponent(item.call_id)}`}>View details</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {page.next_cursor ? (
        <div className="operate-pagination">
          <Link className="button button--secondary" href={`/conversations?cursor=${encodeURIComponent(page.next_cursor)}`}>Next page</Link>
        </div>
      ) : null}
    </section>
  );
}
