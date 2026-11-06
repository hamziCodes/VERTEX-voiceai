import Link from "next/link";

import { hasWorkspacePermission, type WorkspacePermission, type WorkspaceRole } from "@/auth/workspace-permissions";

const ITEMS: ReadonlyArray<{ label: string; href: string; permission: WorkspacePermission }> = [
  { label: "Conversations", href: "/conversations", permission: "conversation:read" },
  { label: "Usage", href: "/settings/usage", permission: "usage:read" },
  { label: "Audit", href: "/settings/audit", permission: "audit:read" },
];

export function OperationsNavigation({ role }: { role: WorkspaceRole }) {
  return (
    <nav aria-label="Operations">
      {ITEMS.filter((item) => hasWorkspacePermission(role, item.permission)).map((item) => (
        <Link href={item.href} key={item.label}>{item.label}</Link>
      ))}
    </nav>
  );
}
