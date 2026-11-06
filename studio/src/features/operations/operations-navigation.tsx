import Link from "next/link";

import { hasWorkspaceCapability, type WorkspaceCapability } from "@/auth/capabilities";

const ITEMS: ReadonlyArray<{ label: string; href: string; permission: WorkspaceCapability }> = [
  { label: "Conversations", href: "/conversations", permission: "conversation:read" },
  { label: "Usage", href: "/settings/usage", permission: "usage:read" },
  { label: "Audit", href: "/settings/audit", permission: "audit:read" },
];

export function OperationsNavigation({ capabilities }: { capabilities: readonly string[] }) {
  return (
    <nav aria-label="Operations">
      {ITEMS.filter((item) => hasWorkspaceCapability(capabilities, item.permission)).map((item) => (
        <Link href={item.href} key={item.label}>{item.label}</Link>
      ))}
    </nav>
  );
}
