import Link from "next/link";

import { hasPlatformCapability, requirePlatform } from "@/auth/platform";
import { PageHeader } from "@/components/studio/page-header";
import { StatePanel } from "@/components/studio/state-panel";
import { StatusBadge } from "@/components/studio/status-badge";
import type { SupportSessionDto } from "@/data/schema";
import { endSupportSessionAction } from "@/features/admin/actions";
import { loadSupportSessions } from "@/features/admin/data";
import { EndSupportSession } from "@/features/admin/end-support-session";
import { STATE_LABELS, scopeList } from "@/features/admin/support-session-views";
import { formatDateTime } from "@/lib/format";

function SessionTable({ canEnd, label, sessions }: { canEnd(session: SupportSessionDto): boolean; label: string; sessions: SupportSessionDto[] }) {
  return (
    <table aria-label={label} className="data-table">
      <thead>
        <tr>
          <th scope="col">Tenant</th>
          <th scope="col">Staff member</th>
          <th scope="col">Scopes</th>
          <th scope="col">Started</th>
          <th scope="col">State</th>
          <th scope="col"><span className="sr-only">Actions</span></th>
        </tr>
      </thead>
      <tbody>
        {sessions.map((session) => (
          <tr key={session.session_id}>
            <td data-label="Tenant"><strong>{session.tenant_name}</strong>{session.reference ? <span className="muted-copy support-agent__meta">{session.reference}</span> : null}</td>
            <td data-label="Staff member">{session.actor_email ?? "Unknown email"}</td>
            <td data-label="Scopes">{scopeList(session.scopes)}</td>
            <td data-label="Started"><span className="technical-value">{formatDateTime(session.created_at)}</span></td>
            <td data-label="State"><StatusBadge tone={STATE_LABELS[session.state].tone}>{STATE_LABELS[session.state].label}</StatusBadge></td>
            <td className="data-table__actions" data-label="Actions">
              <div className="admin-staff__actions">
                <Link aria-label={`Open support session for ${session.tenant_name}`} className="button button--secondary" href={`/admin/support-sessions/${session.session_id}`}>Open</Link>
                {canEnd(session) ? <EndSupportSession compact onEnd={endSupportSessionAction} sessionId={session.session_id} tenantName={session.tenant_name} /> : null}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default async function SupportSessionsPage() {
  const { identity, session } = await requirePlatform("platform_support_session:read");
  const [active, recent] = await Promise.all([loadSupportSessions(session, "active"), loadSupportSessions(session, "recent")]);
  const canWrite = hasPlatformCapability(identity.capabilities, "platform_support_session:write");
  const canManage = hasPlatformCapability(identity.capabilities, "platform_support_session:manage");
  const canEnd = (item: SupportSessionDto) => item.state === "active" && canWrite && (item.actor_user_id === identity.user_id || canManage);

  return (
    <section className="admin-page">
      <PageHeader
        eyebrow="Wavia admin"
        summary="Read-only, expiring access to a tenant's safe configuration and readiness. Start a session from a tenant summary; every start, view and end is audited."
        title="Support sessions"
      />
      <section aria-labelledby="support-active-heading" className="form-panel operate-panel">
        <h2 className="operate-panel__title" id="support-active-heading">Active</h2>
        {active.length === 0 ? (
          <StatePanel
            actions={<Link className="button button--secondary" href="/admin/tenants">Find a tenant</Link>}
            description="Open a tenant summary and choose Start support session."
            title="No active support sessions"
          />
        ) : <SessionTable canEnd={canEnd} label="Active support sessions" sessions={active} />}
      </section>
      <section aria-labelledby="support-recent-heading" className="form-panel operate-panel">
        <h2 className="operate-panel__title" id="support-recent-heading">Recent</h2>
        {recent.length === 0 ? <p className="muted-copy">No support sessions have been started.</p> : <SessionTable canEnd={canEnd} label="Recent support sessions" sessions={recent} />}
      </section>
    </section>
  );
}
