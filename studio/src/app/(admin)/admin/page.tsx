import Link from "next/link";

import { hasPlatformCapability, requirePlatform, type PlatformCapability } from "@/auth/platform";
import { PageHeader } from "@/components/studio/page-header";
import { StatusBadge } from "@/components/studio/status-badge";
import { PLATFORM_ROLE_DETAILS } from "@/features/admin/types";

const DESTINATIONS: ReadonlyArray<{ href: string; title: string; description: string; capability: PlatformCapability }> = [
  { href: "/admin/tenants", title: "Tenants", description: "Search the tenant directory and open safe tenant summaries.", capability: "platform_tenant:read" },
  { href: "/admin/support-sessions", title: "Support sessions", description: "Open, review and end read-only, expiring support sessions.", capability: "platform_support_session:read" },
  { href: "/admin/operations", title: "Operations", description: "Check database, identity, post-call queue and live-traffic gates.", capability: "platform_operations:read" },
  { href: "/admin/staff", title: "Staff", description: "Grant, change and revoke Wavia platform roles with a recorded reason.", capability: "platform_staff:read" },
  { href: "/admin/audit", title: "Audit", description: "Review platform staff changes and tenant summary views.", capability: "platform_audit:read" },
];

const ERROR_MESSAGES: Record<string, string> = {
  forbidden: "Your platform role cannot open that area.",
};

export default async function AdminOverviewPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error = "" } = await searchParams;
  const { identity } = await requirePlatform();
  const available = DESTINATIONS.filter((item) => hasPlatformCapability(identity.capabilities, item.capability));
  const role = PLATFORM_ROLE_DETAILS[identity.role];

  return (
    <section className="admin-page">
      <PageHeader
        eyebrow="Wavia admin"
        summary="Internal tools for Wavia staff. Only areas your platform role can open are listed."
        title="Platform overview"
      />
      {ERROR_MESSAGES[error] ? <div className="inline-notice inline-notice--danger" role="alert">{ERROR_MESSAGES[error]}</div> : null}
      <section aria-labelledby="admin-role-heading" className="form-panel admin-role">
        <div className="admin-role__heading">
          <h2 className="operate-panel__title" id="admin-role-heading">Your platform role</h2>
          <StatusBadge tone="info">{role.label}</StatusBadge>
        </div>
        <p className="muted-copy">{role.description}</p>
        <p className="muted-copy">Platform roles do not grant access to customer workspaces.</p>
      </section>
      <ul aria-label="Platform areas" className="settings-list">
        {available.map((item) => (
          <li key={item.href}>
            <Link className="settings-link" href={item.href}>
              <span className="settings-link__copy">
                <strong>{item.title}</strong>
                <span>{item.description}</span>
              </span>
              <span aria-hidden="true" className="settings-link__arrow">→</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
