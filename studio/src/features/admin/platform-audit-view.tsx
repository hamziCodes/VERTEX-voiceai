import Link from "next/link";

import { StatePanel } from "@/components/studio/state-panel";
import type { PlatformAuditEventDto } from "@/data/schema";
import { formatDateTime } from "@/lib/format";

import { AUDIT_ACTION_LABELS, PLATFORM_ROLE_DETAILS } from "./types";

function shortId(value: string): string {
  return value.slice(0, 8);
}

function roleChange(event: PlatformAuditEventDto): string | null {
  const previous = event.previous_role ? PLATFORM_ROLE_DETAILS[event.previous_role].label : null;
  const next = event.new_role ? PLATFORM_ROLE_DETAILS[event.new_role].label : null;
  if (previous && next) return `${previous} → ${next}`;
  if (next) return `Granted ${next}`;
  if (previous) return `Removed ${previous}`;
  return null;
}

function Target({ event }: { event: PlatformAuditEventDto }) {
  if (event.target_tenant_id) {
    return (
      <Link className="admin-tenant-link" href={`/admin/tenants/${event.target_tenant_id}`}>
        Tenant <span className="technical-value">{shortId(event.target_tenant_id)}</span>
      </Link>
    );
  }
  if (event.target_user_id) return <span>Staff member <span className="technical-value">{shortId(event.target_user_id)}</span></span>;
  return <span className="muted-copy">—</span>;
}

export function PlatformAuditView({ events, limit }: { events: PlatformAuditEventDto[]; limit: number }) {
  if (events.length === 0) {
    return <StatePanel description="Staff role changes and tenant summary views will appear here." title="No platform events yet" />;
  }
  return (
    <section aria-labelledby="platform-audit-heading" className="form-panel operate-panel">
      <div className="operate-panel__heading">
        <h2 className="operate-panel__title" id="platform-audit-heading">Recent events</h2>
        <p className="muted-copy admin-directory__count">Latest {limit} events, newest first.</p>
      </div>
      <table aria-label="Platform audit events" className="data-table">
        <thead>
          <tr>
            <th scope="col">Time</th>
            <th scope="col">Action</th>
            <th scope="col">Actor</th>
            <th scope="col">Target</th>
            <th scope="col">Details</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => {
            const change = roleChange(event);
            return (
              <tr key={event.event_id}>
                <td data-label="Time"><span className="technical-value">{formatDateTime(event.created_at)}</span></td>
                <td data-label="Action">
                  {AUDIT_ACTION_LABELS[event.action] ?? <span className="technical-value">{event.action}</span>}
                </td>
                <td data-label="Actor">
                  {event.actor_user_id ? <span className="technical-value">{shortId(event.actor_user_id)}</span> : "System migration"}
                </td>
                <td data-label="Target"><Target event={event} /></td>
                <td data-label="Details">
                  <span className="admin-audit__details">
                    {change ? <span>{change}</span> : null}
                    {event.scope ? <span>Scope: {event.scope}</span> : null}
                    {event.reason ? <span className="muted-copy">{event.reason}</span> : null}
                    {!change && !event.reason && !event.scope ? <span className="muted-copy">—</span> : null}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
