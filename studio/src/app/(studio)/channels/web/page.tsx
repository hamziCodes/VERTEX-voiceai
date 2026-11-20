import { requireWorkspace } from "@/auth/workspace";
import { loadAgents } from "@/features/agents/data";
import { ChannelsHeader } from "@/features/channels/channels-header";
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
    <section className="channels-page">
      <ChannelsHeader />
      <WebChannelView agents={summaries} />
    </section>
  );
}
