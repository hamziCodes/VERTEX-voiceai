"use client";

import { hasPlatformCapability, type PlatformCapability } from "@/auth/platform-permissions";
import { SidebarShell, startsWith, type SidebarItem } from "@/components/studio/sidebar-shell";
import type { PlatformRole } from "@/data/schema";

type AdminItem = SidebarItem & { permission?: PlatformCapability };

const ITEMS: ReadonlyArray<AdminItem> = [
  { label: "Overview", shortLabel: "O", href: "/admin", active: (path) => path === "/admin" },
  { label: "Tenants", shortLabel: "T", href: "/admin/tenants", permission: "platform_tenant:read", active: startsWith("/admin/tenants") },
  { label: "Staff", shortLabel: "S", href: "/admin/staff", permission: "platform_staff:read", active: startsWith("/admin/staff") },
  { label: "Audit", shortLabel: "A", href: "/admin/audit", permission: "platform_audit:read", active: startsWith("/admin/audit") },
];

/** Internal-only navigation. It never lists customer workspace routes. */
export function AdminNavigation({
  capabilities,
  displayName,
  role,
  signOutAction,
}: {
  capabilities: readonly string[];
  displayName?: string;
  role: PlatformRole;
  signOutAction?: () => Promise<void>;
}) {
  const items = ITEMS.filter((item) => !item.permission || hasPlatformCapability(capabilities, item.permission));
  // Short form, like the workspace shell ("tenant admin"); the overview shows the full label.
  const roleLabel = role === "platform_admin" ? "platform admin" : "platform support";
  return (
    <SidebarShell
      account={displayName ? { displayName, roleLabel, signOutAction } : undefined}
      brandHref="/admin"
      brandText="Wavia admin"
      context={(
        <div className="studio-workspace studio-workspace--internal" title="Internal Wavia area">
          <span aria-hidden="true" className="studio-workspace__mark">i</span>
          <span className="studio-workspace__copy">
            <span className="studio-workspace__eyebrow">Internal area</span>
            <strong>Wavia staff only</strong>
          </span>
        </div>
      )}
      groups={[{ label: "Platform", items }]}
      id="studio-admin-navigation"
      navLabel="Wavia admin"
    />
  );
}
