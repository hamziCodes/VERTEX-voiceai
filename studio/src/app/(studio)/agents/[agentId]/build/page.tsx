import { notFound } from "next/navigation";
import { z } from "zod";

import { hasWorkspacePermission, requireWorkspace } from "@/auth/workspace";
import { publishAgentDraftAction, restoreAgentVersionAction, saveAgentDraftAction, validateAgentDraftAction } from "@/features/agents/actions";
import { AgentDraftEditor } from "@/features/agents/agent-draft-editor";
import { loadAgent, loadAgentValidation, loadAgentVersions } from "@/features/agents/data";

export default async function AgentBuildPage({ params }: { params: Promise<{ agentId: string }> }) {
  const { agentId } = await params;
  if (!z.string().uuid().safeParse(agentId).success) notFound();
  const { session, membership } = await requireWorkspace("agent:read");
  const [agent, validation, versions] = await Promise.all([
    loadAgent(session, membership.tenant_id, agentId),
    loadAgentValidation(session, membership.tenant_id, agentId),
    loadAgentVersions(session, membership.tenant_id, agentId),
  ]);
  return (
    <>
      <h1>Build {agent.name}</h1>
      <p>Changes save automatically. Publishing creates an immutable version for new sessions.</p>
      <AgentDraftEditor
        actions={{
          saveDraft: saveAgentDraftAction,
          validateDraft: validateAgentDraftAction,
          publishDraft: publishAgentDraftAction,
          restoreVersion: restoreAgentVersionAction,
        }}
        canEdit={hasWorkspacePermission(membership.role, "agent:write")}
        initialAgent={agent}
        initialValidation={validation}
        versions={versions}
      />
    </>
  );
}
