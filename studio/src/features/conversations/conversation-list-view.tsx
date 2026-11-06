"use client";

import Link from "next/link";
import { useState } from "react";

import type { ConversationPageDto } from "./types";

function transportLabel(value: string): string {
  if (value === "sip") return "SIP";
  if (value === "websocket") return "Web";
  return value;
}

export function ConversationListView({ page }: { page: ConversationPageDto }) {
  const [transport, setTransport] = useState("all");
  const [disposition, setDisposition] = useState("all");
  const visible = page.items.filter((item) =>
    (transport === "all" || item.transport_type === transport)
    && (disposition === "all" || item.disposition === disposition)
  );

  if (page.items.length === 0) {
    return (
      <section aria-labelledby="conversation-history-heading">
        <h2 id="conversation-history-heading">Conversation history</h2>
        <p>No conversations have been recorded for this workspace.</p>
      </section>
    );
  }

  const transports = [...new Set(page.items.map((item) => item.transport_type))];
  const dispositions = [...new Set(page.items.map((item) => item.disposition))];

  return (
    <section aria-labelledby="conversation-history-heading">
      <h2 id="conversation-history-heading">Conversation history</h2>
      <div>
        <label htmlFor="conversation-transport">Transport</label>{" "}
        <select id="conversation-transport" value={transport} onChange={(event) => setTransport(event.target.value)}>
          <option value="all">All</option>
          {transports.map((value) => <option key={value} value={value}>{transportLabel(value)}</option>)}
        </select>{" "}
        <label htmlFor="conversation-disposition">Disposition</label>{" "}
        <select id="conversation-disposition" value={disposition} onChange={(event) => setDisposition(event.target.value)}>
          <option value="all">All</option>
          {dispositions.map((value) => <option key={value} value={value}>{value}</option>)}
        </select>
        <p>Filters apply to this loaded page. Use pagination to inspect additional records.</p>
      </div>

      {visible.length === 0 ? (
        <p>No conversations on this page match the selected filters.</p>
      ) : (
        <table>
          <thead>
            <tr><th>Started</th><th>Transport</th><th>Disposition</th><th>Turns</th><th>Recording</th><th>Open</th></tr>
          </thead>
          <tbody>
            {visible.map((item) => (
              <tr key={item.call_id}>
                <td>{new Date(item.started_at).toLocaleString()}</td>
                <td>{transportLabel(item.transport_type)}</td>
                <td>{item.disposition}</td>
                <td>{item.turn_count}</td>
                <td>{item.recording_state}</td>
                <td><Link href={`/conversations/${encodeURIComponent(item.call_id)}`}>View details</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {page.next_cursor && (
        <Link href={`/conversations?cursor=${encodeURIComponent(page.next_cursor)}`}>Next page</Link>
      )}
    </section>
  );
}
