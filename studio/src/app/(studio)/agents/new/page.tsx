import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { createAgentAction } from "@/features/agents/actions";
import { AgentCreationWizard } from "@/features/agents/agent-creation-wizard";
import { loadAgents, loadEntitlements, loadTemplates } from "@/features/agents/data";

export default async function NewAgentPage() {
  const { session, membership } = await requireWorkspace("agent:read");
  const [agents, entitlements, templates] = await Promise.all([
    loadAgents(session, membership.tenant_id),
    loadEntitlements(session, membership.tenant_id),
    loadTemplates(session, membership.tenant_id),
  ]);
  return (
    <>
      <h1>Create an agent</h1>
      <p>Choose a tested starting point or begin with the default safe configuration.</p>
      <AgentCreationWizard
        agentCount={agents.length}
        canEdit={hasWorkspaceCapability(membership.capabilities, "agent:write")}
        createAction={createAgentAction}
        maxAgents={entitlements.max_agents}
        templates={templates}
      />
    </>
  );
}
