import Link from "next/link";
import { requireWorkspace } from "@/auth/workspace";
import { loadAgents } from "@/features/agents/data";
import { WebChannelView } from "@/features/channels/web-channel-view";

export default async function WebChannelPage() {
  const { session, membership } = await requireWorkspace("agent:read");
  const agents = await loadAgents(session, membership.tenant_id);

  const summaries = agents.map((a) => ({
    agent_id: a.agent_id,
    name: a.name,
    is_published: a.is_published,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <nav aria-label="Channel tabs" style={{ display: "flex", gap: "1rem", borderBottom: "1px solid #e4e4e7", paddingBottom: "0.5rem" }}>
        <Link href="/channels/web" style={{ fontWeight: 600, color: "#18181b", borderBottom: "2px solid #18181b", paddingBottom: "0.5rem" }}>
          Web Embed
        </Link>
        <Link href="/channels/telephony" style={{ color: "#71717a", paddingBottom: "0.5rem" }}>
          Telephony
        </Link>
      </nav>

      <WebChannelView agents={summaries} />
    </div>
  );
}
