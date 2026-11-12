import Link from "next/link";

import { hasWorkspaceCapability, requireWorkspace, type WorkspaceCapability } from "@/auth/workspace";
import { PageHeader } from "@/components/studio/page-header";
import { StatePanel } from "@/components/studio/state-panel";

const DESTINATIONS: ReadonlyArray<{ href: string; title: string; description: string; capability: WorkspaceCapability }> = [
  { href: "/settings/members", title: "Members", description: "See who has access, invite people and manage workspace roles.", capability: "member:read" },
  { href: "/settings/usage", title: "Usage", description: "Review quota consumption and recorded usage totals.", capability: "usage:read" },
  { href: "/settings/audit", title: "Audit", description: "Inspect recorded workspace and system events.", capability: "audit:read" },
  { href: "/settings/providers", title: "Provider credentials", description: "Review provider readiness and credential metadata.", capability: "provider_credential:read" },
];

export default async function SettingsPage() {
  const { membership } = await requireWorkspace();
  const available = DESTINATIONS.filter((item) => hasWorkspaceCapability(membership.capabilities, item.capability));

  return (
    <section className="settings-page">
      <PageHeader eyebrow="Workspace" summary={`Settings for ${membership.tenant_name}. Only areas your role can open are listed.`} title="Settings" />
      {available.length === 0 ? (
        <StatePanel description="Your role does not include workspace settings. Ask a workspace administrator if you need access." title="No workspace settings for your role" />
      ) : (
        <ul aria-label="Workspace settings" className="settings-list">
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
      )}
    </section>
  );
}
