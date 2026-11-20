"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function AgentWorkspaceTabs({ agentId }: { agentId: string }) {
  const pathname = usePathname();
  const base = `/agents/${encodeURIComponent(agentId)}`;
  const tabs = [
    { href: `${base}/build`, label: "Persona", active: pathname.endsWith("/build") },
    { href: `${base}/test`, label: "Test sandbox", active: pathname.endsWith("/test") },
  ] as const;

  return (
    <nav aria-label="Agent workspace" className="agent-tabs">
      {tabs.map((tab) => (
        <Link aria-current={tab.active ? "page" : undefined} className="agent-tabs__link" href={tab.href} key={tab.label}>
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
