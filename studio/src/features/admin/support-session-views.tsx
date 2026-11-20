import Link from "next/link";
import type { ReactNode } from "react";

import { StatusBadge } from "@/components/studio/status-badge";
import type { SupportConfigurationDto, SupportReadinessDto, SupportSessionDto } from "@/data/schema";
import { formatDateTime, formatNumber } from "@/lib/format";

import { SUPPORT_SCOPE_DETAILS } from "./types";

export const STATE_LABELS: Readonly<Record<SupportSessionDto["state"], { label: string; tone: "success" | "neutral" | "warning" }>> = {
  active: { label: "Active", tone: "success" },
  expired: { label: "Expired", tone: "neutral" },
  ended: { label: "Ended", tone: "neutral" },
};

export function scopeList(scopes: SupportSessionDto["scopes"]): string {
  return scopes.map((scope) => SUPPORT_SCOPE_DETAILS[scope].label).join(", ");
}

function yesNo(value: boolean, yes = "Enabled", no = "Disabled") {
  return <StatusBadge tone={value ? "success" : "neutral"}>{value ? yes : no}</StatusBadge>;
}

/** Persistent banner shown while an active session's tenant data is on screen. */
export function SupportSessionBanner({ actions, session }: { actions?: ReactNode; session: SupportSessionDto }) {
  return (
    <section aria-label="Support session" className="support-banner">
      <div className="support-banner__copy">
        <StatusBadge tone="warning">Read-only</StatusBadge>
        <p>
          Support session for <strong>{session.tenant_name}</strong>
          <span aria-hidden="true" className="support-banner__separator">·</span>
          <span className="technical-value">Ends {formatDateTime(session.expires_at)}</span>
        </p>
      </div>
      {actions ? <div className="support-banner__actions">{actions}</div> : null}
    </section>
  );
}

export function SupportSessionDetails({ session }: { session: SupportSessionDto }) {
  return (
    <section aria-labelledby="support-details-heading" className="form-panel operate-panel">
      <h2 className="operate-panel__title" id="support-details-heading">Session details</h2>
      <dl className="detail-grid">
        <div><dt>Tenant</dt><dd><Link className="admin-tenant-link" href={`/admin/tenants/${session.tenant_id}`}>{session.tenant_name}</Link></dd></div>
        <div><dt>Staff member</dt><dd>{session.actor_email ?? "Unknown email"}</dd></div>
        <div><dt>Scopes</dt><dd>{scopeList(session.scopes)}</dd></div>
        <div><dt>State</dt><dd><StatusBadge tone={STATE_LABELS[session.state].tone}>{STATE_LABELS[session.state].label}</StatusBadge></dd></div>
        <div><dt>Started</dt><dd className="technical-value">{formatDateTime(session.created_at)}</dd></div>
        <div><dt>{session.state === "ended" ? "Ended" : "Ends"}</dt><dd className="technical-value">{formatDateTime(session.ended_at ?? session.expires_at)}</dd></div>
        <div><dt>Reason</dt><dd>{session.reason}</dd></div>
        <div><dt>Reference</dt><dd>{session.reference ?? "—"}</dd></div>
      </dl>
    </section>
  );
}

export function SupportConfigurationView({ data }: { data: SupportConfigurationDto }) {
  return (
    <section aria-labelledby="support-configuration-heading" className="form-panel operate-panel">
      <h2 className="operate-panel__title" id="support-configuration-heading">Configuration</h2>
      <p className="muted-copy support-section__note">Counts and status only. Prompts, greetings, tool definitions and credentials are never shown.</p>
      {data.agents.length === 0 ? <p className="muted-copy">This tenant has no agents.</p> : (
        <table aria-label="Agents" className="data-table">
          <thead>
            <tr>
              <th scope="col">Agent</th>
              <th scope="col">Status</th>
              <th scope="col">Languages</th>
              <th scope="col">Provider routes</th>
              <th scope="col">Tools · knowledge</th>
              <th scope="col">Telephony</th>
            </tr>
          </thead>
          <tbody>
            {data.agents.map((agent) => (
              <tr key={agent.agent_id}>
                <td data-label="Agent"><strong>{agent.name}</strong><span className="muted-copy support-agent__meta">Version {agent.version} · draft {agent.draft_revision}</span></td>
                <td data-label="Status"><StatusBadge tone={agent.is_published ? "success" : "neutral"}>{agent.is_published ? "Published" : "Draft"}</StatusBadge></td>
                <td data-label="Languages">{agent.languages.join(", ")}</td>
                <td data-label="Provider routes"><span className="technical-value">{Object.entries(agent.provider_route_counts).map(([stage, count]) => `${stage.toUpperCase()} ${count}`).join(" · ")}</span></td>
                <td data-label="Tools · knowledge">{formatNumber(agent.tool_count)} tools · {formatNumber(agent.knowledge_base_count)} bases</td>
                <td data-label="Telephony">{yesNo(agent.telephony_configured, "Configured", "Not configured")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h3 className="support-section__subtitle">Knowledge bases</h3>
      {data.knowledge_bases.length === 0 ? <p className="muted-copy">This tenant has no knowledge bases.</p> : (
        <table aria-label="Knowledge bases" className="data-table">
          <thead>
            <tr>
              <th scope="col">Knowledge base</th>
              <th scope="col">Status</th>
              <th scope="col">Sources ready</th>
              <th scope="col">Updated</th>
            </tr>
          </thead>
          <tbody>
            {data.knowledge_bases.map((base) => (
              <tr key={base.knowledge_base_id}>
                <td data-label="Knowledge base"><strong>{base.name}</strong></td>
                <td data-label="Status"><StatusBadge>{base.status.replaceAll("_", " ")}</StatusBadge></td>
                <td data-label="Sources ready">{formatNumber(base.ready_source_count)} of {formatNumber(base.source_count)}</td>
                <td data-label="Updated"><span className="technical-value">{formatDateTime(base.updated_at)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export function SupportReadinessView({ data }: { data: SupportReadinessDto }) {
  const entitlements = data.entitlements;
  return (
    <section aria-labelledby="support-readiness-heading" className="form-panel operate-panel">
      <h2 className="operate-panel__title" id="support-readiness-heading">Readiness</h2>
      <dl className="detail-grid">
        <div><dt>Setup steps done</dt><dd>{data.onboarding ? (data.onboarding.completed_steps.join(", ") || "None yet") : "Not available"}</dd></div>
        <div><dt>Use case</dt><dd>{data.onboarding?.use_case ? data.onboarding.use_case.replaceAll("_", " ") : "—"}</dd></div>
        <div><dt>Telephony entitled</dt><dd>{yesNo(data.telephony.telephony_entitled, "Yes", "No")}</dd></div>
        <div><dt>Trunk configured</dt><dd>{yesNo(data.telephony.trunk_configured, "Yes", "No")}</dd></div>
        <div><dt>Carrier health</dt><dd><StatusBadge>Not measured</StatusBadge></dd></div>
        {entitlements ? (
          <>
            <div><dt>Agent limit</dt><dd>{formatNumber(entitlements.max_agents)}</dd></div>
            <div><dt>Concurrent sessions</dt><dd>{formatNumber(entitlements.max_concurrent_sessions)}</dd></div>
            <div><dt>API keys allowed</dt><dd>{formatNumber(entitlements.api_keys_allowed)}</dd></div>
            <div><dt>Advanced providers</dt><dd>{yesNo(entitlements.advanced_providers_enabled)}</dd></div>
          </>
        ) : <div><dt>Entitlements</dt><dd>Not recorded</dd></div>}
      </dl>
    </section>
  );
}
