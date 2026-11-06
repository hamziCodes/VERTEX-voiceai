import type { AuditEventDto } from "./types";

export function AuditView({ events }: { events: AuditEventDto[] }) {
  return (
    <section aria-labelledby="audit-heading">
      <h2 id="audit-heading">Audit history</h2>
      {events.length === 0 ? <p>No audit events are available for this workspace.</p> : (
        <table>
          <thead><tr><th>Time</th><th>Action</th><th>Resource</th><th>Actor type</th></tr></thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.id}>
                <td>{new Date(event.created_at).toLocaleString()}</td>
                <td>{event.action}</td>
                <td>{event.resource_type}</td>
                <td>{event.actor_type}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
