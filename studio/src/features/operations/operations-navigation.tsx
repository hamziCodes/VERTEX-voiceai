import { hasWorkspaceCapability, type WorkspaceCapability } from "@/auth/capabilities";
import { RouteTabs, type RouteTab } from "@/components/studio/route-tabs";

const ITEMS: ReadonlyArray<RouteTab & { permission: WorkspaceCapability }> = [
  { label: "Conversations", href: "/conversations", permission: "conversation:read", matchNested: true },
  { label: "Usage", href: "/settings/usage", permission: "usage:read" },
  { label: "Audit", href: "/settings/audit", permission: "audit:read" },
];

export function OperationsNavigation({ capabilities }: { capabilities: readonly string[] }) {
  return (
    <RouteTabs
      items={ITEMS.filter((item) => hasWorkspaceCapability(capabilities, item.permission)).map((item) => ({ href: item.href, label: item.label, matchNested: item.matchNested }))}
      label="Operations"
    />
  );
}
