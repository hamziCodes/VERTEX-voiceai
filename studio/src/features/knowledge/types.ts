export type KnowledgeBaseStatus = "draft" | "processing" | "ready" | "active" | "failed" | "deleting";
export type KnowledgeSourceStatus = "uploaded" | "queued" | "parsing" | "chunking" | "embedding" | "ready" | "failed" | "deleting";

export interface KnowledgeBaseDto {
  knowledge_base_id: string;
  name: string;
  status: KnowledgeBaseStatus;
  active_revision: number;
  source_count: number;
  ready_source_count: number;
  total_chunks: number;
}

export interface KnowledgeSourceDto {
  source_id: string;
  knowledge_base_id: string;
  source_type: string;
  display_name: string;
  media_type: string;
  byte_count: number;
  revision: number;
  status: KnowledgeSourceStatus;
  chunk_count: number;
  error_code: string | null;
  error_message: string | null;
}

export interface KnowledgePreviewResultDto {
  source_id: string;
  text: string;
  citation: Record<string, unknown>;
  score: number | null;
}

export interface KnowledgeAgentOption {
  agent_id: string;
  name: string;
}

export type KnowledgeActionError = { state: "error"; message: string };

export interface KnowledgeActions {
  createBase(name: string): Promise<{ state: "created"; knowledgeBase: KnowledgeBaseDto } | KnowledgeActionError>;
  uploadSource(knowledgeBaseId: string, file: File): Promise<{ state: "uploaded"; source: KnowledgeSourceDto } | KnowledgeActionError>;
  addFaq(knowledgeBaseId: string, input: { name: string; question: string; answer: string }): Promise<{ state: "uploaded"; source: KnowledgeSourceDto } | KnowledgeActionError>;
  deleteSource(knowledgeBaseId: string, sourceId: string): Promise<{ state: "deleted" } | KnowledgeActionError>;
  retrySource(knowledgeBaseId: string, sourceId: string): Promise<{ state: "queued"; sourceId: string } | KnowledgeActionError>;
  preview(knowledgeBaseId: string, query: string): Promise<{ state: "complete"; results: KnowledgePreviewResultDto[] } | KnowledgeActionError>;
  activate(knowledgeBaseId: string): Promise<{ state: "active"; knowledgeBase: KnowledgeBaseDto } | KnowledgeActionError>;
  bindAgent(knowledgeBaseId: string, agentId: string): Promise<{ state: "bound"; agentVersion: number; knowledgeRevision: number } | KnowledgeActionError>;
}
