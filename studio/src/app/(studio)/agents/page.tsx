import { hasWorkspacePermission, requireWorkspace } from "@/auth/workspace";
import { AgentDirectory } from "@/features/agents/agent-directory";
import { loadAgents, loadEntitlements } from "@/features/agents/data";

export default async function AgentsPage() {
  const { session, membership } = await requireWorkspace("agent:read");
  const [agents, entitlements] = await Promise.all([
    loadAgents(session, membership.tenant_id),
    loadEntitlements(session, membership.tenant_id),
  ]);
  const canEdit = hasWorkspacePermission(membership.role, "agent:write");
  const canCreate = canEdit && agents.length < entitlements.max_agents;

  return <AgentDirectory agents={agents} canCreate={canCreate} canEdit={canEdit} maxAgents={entitlements.max_agents} />;
}
