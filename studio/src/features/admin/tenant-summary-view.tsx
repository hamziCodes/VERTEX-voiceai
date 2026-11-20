import { StatusBadge } from "@/components/studio/status-badge";
import type { StudioRole, TenantSummaryDto } from "@/data/schema";
import { LAUNCH_ROLES, ROLE_DETAILS } from "@/features/members/types";
import { formatDate, formatNumber } from "@/lib/format";

function enabled(value: boolean) {
  return <StatusBadge tone={value ? "success" : "neutral"}>{value ? "Enabled" : "Disabled"}</StatusBadge>;
}

function megabytes(bytes: number): string {
  return `${formatNumber(Math.round(bytes / 1_048_576))} MB`;
}

export function TenantSummaryView({ summary }: { summary: TenantSummaryDto }) {
  const roles = LAUNCH_ROLES.filter((role: StudioRole) => (summary.members_by_role[role] ?? 0) > 0);
  const memberTotal = roles.reduce((sum, role) => sum + (summary.members_by_role[role] ?? 0), 0);
  const entitlements = summary.entitlements;

  return (
    <div className="admin-tenant">
      <div className="inline-notice inline-notice--info">
        <strong>Safe summary only.</strong>
        <p>Conversations, transcripts, recordings and credentials are not shown in the internal area. Opening this summary was recorded in the platform audit.</p>
      </div>

      <section aria-labelledby="tenant-profile-heading" className="form-panel operate-panel">
        <h2 className="operate-panel__title" id="tenant-profile-heading">Profile</h2>
        <dl className="detail-grid">
          <div><dt>Tenant ID</dt><dd><span className="technical-value">{summary.tenant_id}</span></dd></div>
          <div><dt>Created</dt><dd>{formatDate(summary.created_at)}</dd></div>
          <div><dt>Agents</dt><dd>{summary.agent_count === null ? "Not available" : formatNumber(summary.agent_count)}</dd></div>
          <div><dt>Members</dt><dd>{formatNumber(memberTotal)}</dd></div>
        </dl>
      </section>

      <div className="admin-tenant__grid">
        <section aria-labelledby="tenant-members-heading" className="form-panel operate-panel">
          <h2 className="operate-panel__title" id="tenant-members-heading">Members by role</h2>
          {roles.length === 0 ? <p className="muted-copy">This tenant has no members.</p> : (
            <ul aria-label="Members by role" className="admin-role-counts">
              {roles.map((role) => (
                <li key={role}>
                  <span>{ROLE_DETAILS[role].label}</span>
                  <strong>{formatNumber(summary.members_by_role[role] ?? 0)}</strong>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="tenant-setup-heading" className="form-panel operate-panel">
          <h2 className="operate-panel__title" id="tenant-setup-heading">Setup progress</h2>
          {summary.onboarding_completed_steps.length === 0 ? <p className="muted-copy">No setup steps are complete.</p> : (
            <ul aria-label="Completed setup steps" className="token-list">
              {summary.onboarding_completed_steps.map((step) => <li key={step}><code>{step}</code></li>)}
            </ul>
          )}
        </section>
      </div>

      <section aria-labelledby="tenant-entitlements-heading" className="form-panel operate-panel">
        <h2 className="operate-panel__title" id="tenant-entitlements-heading">Entitlements</h2>
        {entitlements === null ? <p className="muted-copy">No entitlements are recorded for this tenant.</p> : (
          <dl className="detail-grid">
            <div><dt>Agent limit</dt><dd>{formatNumber(entitlements.max_agents)}</dd></div>
            <div><dt>Concurrent sessions</dt><dd>{formatNumber(entitlements.max_concurrent_sessions)}</dd></div>
            <div><dt>Knowledge storage</dt><dd>{megabytes(entitlements.max_knowledge_bytes)}</dd></div>
            <div><dt>API keys allowed</dt><dd>{formatNumber(entitlements.api_keys_allowed)}</dd></div>
            <div><dt>Telephony</dt><dd>{enabled(entitlements.telephony_enabled)}</dd></div>
            <div><dt>Advanced providers</dt><dd>{enabled(entitlements.advanced_providers_enabled)}</dd></div>
            <div><dt>Bring your own provider</dt><dd>{enabled(entitlements.byok_enabled)}</dd></div>
            <div><dt>Retention options</dt><dd>{entitlements.allowed_retention_days.map((days) => `${days} days`).join(", ")}</dd></div>
          </dl>
        )}
      </section>
    </div>
  );
}
