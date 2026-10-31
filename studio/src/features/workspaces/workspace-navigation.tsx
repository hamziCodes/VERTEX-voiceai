import Link from "next/link";

import { hasWorkspacePermission, type WorkspacePermission, type WorkspaceRole } from "@/auth/workspace";

const ITEMS: ReadonlyArray<{ label: string; href: string; permission: WorkspacePermission }> = [
  { label: "Setup", href: "/onboarding", permission: "onboarding:read" },
  { label: "Build", href: "/agents", permission: "agent:read" },
  { label: "Knowledge", href: "/knowledge", permission: "knowledge:read" },
  { label: "Test", href: "/agents", permission: "session:read" },
  { label: "Connect", href: "/channels", permission: "telephony:write" },
  { label: "Operate", href: "/operations", permission: "usage:read" },
  { label: "Settings", href: "/settings", permission: "member:write" },
];

export function WorkspaceNavigation({ role }: { role: WorkspaceRole }) {
  return (
    <nav aria-label="Workspace">
      {ITEMS.filter((item) => hasWorkspacePermission(role, item.permission)).map((item) => (
        <Link href={item.href} key={item.label}>{item.label}</Link>
      ))}
    </nav>
  );
}
