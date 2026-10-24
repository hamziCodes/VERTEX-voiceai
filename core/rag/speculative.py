"""Speculative retrieval with conservative transcript reconciliation."""

from __future__ import annotations

from uuid import UUID

from core.rag.models import KnowledgeBaseChunk
from core.rag.retriever import RAGRetriever


def normalized_levenshtein(s1: str, s2: str) -> float:
    """Compute normalized Levenshtein distance from zero to one."""
    if s1 == s2:
        return 0.0
    if not s1 or not s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]

    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,  # deletion
                dp[i][j - 1] + 1,  # insertion
                dp[i - 1][j - 1] + cost,  # substitution
            )

    dist = dp[len1][len2]
    max_len = max(len1, len2)
    return dist / float(max_len)


class SpeculativeRetrieval:
    """Manage partial-transcript retrieval and conservative reconciliation."""

    def __init__(self, retriever: RAGRetriever, threshold: float = 0.08) -> None:
        self.retriever = retriever
        self.threshold = threshold
        self.speculative_query: str = ""
        self.speculative_results: list[KnowledgeBaseChunk] = []
        self._scope: tuple[UUID, UUID | None, UUID | None, int | None] | None = None

    async def speculate(
        self,
        partial_transcript: str,
        tenant_id: UUID,
        *,
        agent_id: UUID | None = None,
        knowledge_base_id: UUID | None = None,
        revision: int | None = None,
    ) -> list[KnowledgeBaseChunk]:
        """Issue speculative retrieval on stabilizing STT partial."""
        self.speculative_query = partial_transcript.strip()
        self._scope = (tenant_id, agent_id, knowledge_base_id, revision)
        self.speculative_results = await self.retriever.retrieve(
            self.speculative_query,
            tenant_id=tenant_id,
            agent_id=agent_id,
            knowledge_base_id=knowledge_base_id,
            revision=revision,
        )
        return self.speculative_results

    async def reconcile(
        self,
        final_transcript: str,
        tenant_id: UUID,
        *,
        agent_id: UUID | None = None,
        knowledge_base_id: UUID | None = None,
        revision: int | None = None,
    ) -> list[KnowledgeBaseChunk]:
        """Reconcile final transcript against speculative query.

        If normalized Levenshtein <= 0.08 threshold, reuse speculative results;
        otherwise re-query retriever.
        """
        final_clean = final_transcript.strip()
        scope = (tenant_id, agent_id, knowledge_base_id, revision)
        if (
            not self.speculative_query
            or not self.speculative_results
            or self._scope != scope
        ):
            return await self.retriever.retrieve(
                final_clean,
                tenant_id=tenant_id,
                agent_id=agent_id,
                knowledge_base_id=knowledge_base_id,
                revision=revision,
            )

        dist = normalized_levenshtein(
            self.speculative_query.lower(), final_clean.lower()
        )
        if dist <= self.threshold:
            # Conservative match — reuse speculative result
            return self.speculative_results

        # Divergent final transcript — re-query
        return await self.retriever.retrieve(
            final_clean,
            tenant_id=tenant_id,
            agent_id=agent_id,
            knowledge_base_id=knowledge_base_id,
            revision=revision,
        )
