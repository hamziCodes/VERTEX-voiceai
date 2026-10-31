import { notFound } from "next/navigation";
import { z } from "zod";

import { hasWorkspacePermission, requireWorkspace } from "@/auth/workspace";
import { loadAgent } from "@/features/agents/data";
import { mintVoiceSessionAction } from "@/features/voice-test/actions";
import { configuredVoiceTestMode } from "@/features/voice-test/config";
import { VoiceTestConsole } from "@/features/voice-test/voice-test-console";

export default async function AgentTestPage({ params }: { params: Promise<{ agentId: string }> }) {
  const { agentId } = await params;
  if (!z.string().uuid().safeParse(agentId).success) notFound();
  const { session, membership } = await requireWorkspace("session:read");
  const agent = await loadAgent(session, membership.tenant_id, agentId);
  return (
    <>
      <h1>Browser voice test</h1>
      <p>Check conversation behavior, interruption, and turn timing before connecting a phone number or website.</p>
      {!agent.is_published ? <p role="alert">This agent has no published version. Publish it before starting a test.</p> : null}
      <VoiceTestConsole
        agentId={agent.agent_id}
        agentName={agent.name}
        canStart={agent.is_published && hasWorkspacePermission(membership.role, "session:mint")}
        mintSession={mintVoiceSessionAction}
        mode={configuredVoiceTestMode()}
      />
    </>
  );
}
