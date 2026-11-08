import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { PageHeader } from "@/components/studio/page-header";
import { loadAgents } from "@/features/agents/data";
import { TestAgentSelector } from "@/features/voice-test/test-agent-selector";

export default async function TestPage() {
  const { session, membership } = await requireWorkspace("session:read");
  const agents = await loadAgents(session, membership.tenant_id);

  return (
    <section className="test-selector-page">
      <PageHeader
        eyebrow="Test"
        summary="Choose a published agent to open its browser sandbox. No session starts and no provider is contacted until you explicitly press Start voice test."
        title="Test an agent"
      />
      <TestAgentSelector agents={agents} canStart={hasWorkspaceCapability(membership.capabilities, "session:mint")} />
    </section>
  );
}
