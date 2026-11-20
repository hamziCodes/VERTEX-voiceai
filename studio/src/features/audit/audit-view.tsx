import { formatDateTime } from "@/lib/format";
import { humanize } from "@/features/operations/labels";

import type { AuditEventDto } from "./types";

export function AuditView({ events }: { events: AuditEventDto[] }) {
  return (
    <section aria-labelledby="audit-events-heading" className="form-panel operate-panel">
      <h2 className="operate-panel__title" id="audit-events-heading">Recorded events</h2>
      {events.length === 0 ? <p className="muted-copy">No audit events are available for this workspace.</p> : (
        <table aria-label="Audit events" className="data-table">
          <thead>
            <tr>
              <th scope="col">Time</th>
              <th scope="col">Action</th>
              <th scope="col">Resource</th>
              <th scope="col">Actor type</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.id}>
                <td data-label="Time"><span className="technical-value">{formatDateTime(event.created_at)}</span></td>
                <td data-label="Action"><span className="technical-value">{event.action}</span></td>
                <td data-label="Resource">{humanize(event.resource_type)}</td>
                <td data-label="Actor type">{humanize(event.actor_type)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
