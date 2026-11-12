import Link from "next/link";
import { z } from "zod";

import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { PageHeader } from "@/components/studio/page-header";
import { activateKnowledgeBaseAction, addKnowledgeFaqAction, bindKnowledgeToAgentAction, createKnowledgeBaseAction, deleteKnowledgeSourceAction, previewKnowledgeAction, retryKnowledgeSourceAction, uploadKnowledgeSourceAction } from "@/features/knowledge/actions";
import { loadKnowledgeAgents, loadKnowledgeBases, loadKnowledgeEntitlements, loadKnowledgeSources } from "@/features/knowledge/data";
import { KnowledgeManager } from "@/features/knowledge/knowledge-manager";

export default async function KnowledgePage({ searchParams }: { searchParams: Promise<{ knowledgeBase?: string }> }) {
  const { session, membership } = await requireWorkspace("knowledge:read");
  const [bases, agents, entitlements] = await Promise.all([
    loadKnowledgeBases(session, membership.tenant_id),
    loadKnowledgeAgents(session, membership.tenant_id),
    loadKnowledgeEntitlements(session, membership.tenant_id),
  ]);
  const requested = (await searchParams).knowledgeBase;
  const requestedId = z.string().uuid().safeParse(requested).success ? requested : null;
  const selected = bases.find((base) => base.knowledge_base_id === requestedId) ?? bases[0] ?? null;
  const sources = selected ? await loadKnowledgeSources(session, membership.tenant_id, selected.knowledge_base_id) : [];
  return (
    <section className="knowledge-page">
      <PageHeader
        eyebrow="Create"
        summary="Add trusted business information, verify the retrieved citations, then connect an active revision to an agent."
        title="Knowledge"
      />
      {bases.length > 0 ? (
        <nav aria-label="Knowledge bases" className="route-tabs">
          {bases.map((base) => (
            <Link
              aria-current={base.knowledge_base_id === selected?.knowledge_base_id ? "page" : undefined}
              className="route-tabs__link"
              href={`/knowledge?knowledgeBase=${base.knowledge_base_id}`}
              key={base.knowledge_base_id}
            >
              {base.name}
            </Link>
          ))}
        </nav>
      ) : null}
      <KnowledgeManager
        actions={{
          createBase: createKnowledgeBaseAction,
          uploadSource: uploadKnowledgeSourceAction,
          addFaq: addKnowledgeFaqAction,
          deleteSource: deleteKnowledgeSourceAction,
          retrySource: retryKnowledgeSourceAction,
          preview: previewKnowledgeAction,
          activate: activateKnowledgeBaseAction,
          bindAgent: bindKnowledgeToAgentAction,
        }}
        agents={agents.map((agent) => ({ agent_id: agent.agent_id, name: agent.name }))}
        base={selected}
        canEdit={hasWorkspaceCapability(membership.capabilities, "knowledge:write")}
        // Remount only when the person switches bases; a refresh after creating one keeps local state.
        key={requestedId ?? "default"}
        maxUploadBytes={entitlements.max_knowledge_bytes}
        sources={sources}
      />
    </section>
  );
}
