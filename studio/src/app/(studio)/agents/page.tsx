import Link from "next/link";

import { hasWorkspacePermission, requireWorkspace } from "@/auth/workspace";
import { loadAgents, loadEntitlements } from "@/features/agents/data";

export default async function AgentsPage() {
  const { session, membership } = await requireWorkspace("agent:read");
  const [agents, entitlements] = await Promise.all([
    loadAgents(session, membership.tenant_id),
    loadEntitlements(session, membership.tenant_id),
  ]);
  const canCreate = hasWorkspacePermission(membership.role, "agent:write") && agents.length < entitlements.max_agents;
  return (
    <>
      <h1>Agents</h1>
      <p>{agents.length} of {entitlements.max_agents} agent slots used.</p>
      {canCreate ? <Link href="/agents/new">Create agent</Link> : null}
      {agents.length === 0 ? <p>No agents yet. Start from a guided template or a blank setup.</p> : (
        <ul>
          {agents.map((agent) => (
            <li key={agent.agent_id}>
              <h2>{agent.name}</h2>
              <p>{agent.description || "No description yet."}</p>
              <p>{agent.is_published ? `Published version ${agent.version}` : "Draft"}</p>
              <Link href={`/agents/${agent.agent_id}/build`}>{hasWorkspacePermission(membership.role, "agent:write") ? "Open builder" : "View agent"}</Link>
              {agent.is_published ? <Link href={`/agents/${agent.agent_id}/test`}>Test voice</Link> : null}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
