"use client";

import { hasWorkspaceCapability, type WorkspaceCapability, type WorkspaceRole } from "@/auth/workspace-permissions";
import { SidebarShell, startsWith, type SidebarItem } from "@/components/studio/sidebar-shell";

type NavigationItem = SidebarItem & { permission: WorkspaceCapability };

type NavigationGroup = { label: string; items: ReadonlyArray<NavigationItem> };

const GROUPS: ReadonlyArray<NavigationGroup> = [
  {
    label: "Create",
    items: [
      { label: "Setup", shortLabel: "S", href: "/onboarding", permission: "onboarding:read", active: startsWith("/onboarding") },
      { label: "Build", shortLabel: "B", href: "/agents", permission: "agent:read", active: (path) => startsWith("/agents")(path) && !path.endsWith("/test") },
      { label: "Knowledge", shortLabel: "K", href: "/knowledge", permission: "knowledge:read", active: startsWith("/knowledge") },
      { label: "Test", shortLabel: "T", href: "/test", permission: "session:read", active: (path) => path === "/test" || (path.startsWith("/agents/") && path.endsWith("/test")) },
      { label: "Connect", shortLabel: "C", href: "/channels", permission: "telephony:read", active: startsWith("/channels") },
    ],
  },
  {
    label: "Operate",
    items: [
      { label: "Conversations", shortLabel: "O", screenReaderPrefix: "Operate", href: "/conversations", permission: "conversation:read", active: (path) => startsWith("/conversations")(path) || startsWith("/settings/usage")(path) || startsWith("/settings/audit")(path) },
    ],
  },
  {
    label: "Developer",
    items: [
      { label: "API keys", shortLabel: "A", href: "/developers/api-keys", permission: "api_key:read", active: startsWith("/developers/api-keys") },
      { label: "Webhooks", shortLabel: "H", href: "/developers/webhooks", permission: "webhook:read", active: startsWith("/developers/webhooks") },
      { label: "Providers", shortLabel: "P", href: "/settings/providers", permission: "provider_credential:read", active: startsWith("/settings/providers") },
    ],
  },
  {
    label: "Workspace",
    items: [
      { label: "Settings", shortLabel: "W", href: "/settings", permission: "member:read", active: (path) => path === "/settings" || startsWith("/settings/members")(path) },
    ],
  },
];

export function WorkspaceNavigation({
  capabilities,
  role,
  tenantName,
  displayName,
  signOutAction,
}: {
  capabilities: readonly string[];
  role: WorkspaceRole;
  tenantName?: string;
  displayName?: string;
  signOutAction?: () => Promise<void>;
}) {
  const groups = GROUPS.map((group) => ({
    label: group.label,
    items: group.items.filter((item) => hasWorkspaceCapability(capabilities, item.permission)),
  }));

  return (
    <SidebarShell
      account={displayName ? { displayName, roleLabel: role.replaceAll("_", " "), signOutAction } : undefined}
      brandHref="/dashboard"
      brandText="Wavia Studio"
      context={tenantName ? (
        <div className="studio-workspace" title={tenantName}>
          <span aria-hidden="true" className="studio-workspace__mark">{tenantName.slice(0, 1).toUpperCase()}</span>
          <span className="studio-workspace__copy">
            <span className="studio-workspace__eyebrow">Workspace</span>
            <strong>{tenantName}</strong>
          </span>
        </div>
      ) : null}
      groups={groups}
      id="studio-workspace-navigation"
      navLabel="Workspace"
    />
  );
}
