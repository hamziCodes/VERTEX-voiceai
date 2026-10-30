export interface PersonaDto {
  system_prompt: string;
  greeting: string | null;
  voice_id: string;
  voice_by_language: Record<string, string>;
  persona_isolation: boolean;
}

export interface ProviderRouteDto {
  provider_id: string;
  model?: string | null;
  enabled: boolean;
  priority: number;
}

export interface ProviderChainDto {
  category: string;
  language: string;
  routes: ProviderRouteDto[];
}

export interface ProvidersDto {
  stt: ProviderChainDto[];
  llm: ProviderChainDto[];
  tts: ProviderChainDto[];
  s2s: ProviderChainDto[];
}

export interface AgentDto {
  agent_id: string;
  name: string;
  description: string;
  languages: string[];
  persona: PersonaDto;
  providers: ProvidersDto;
  compliance: Record<string, unknown>;
  draft_revision: number;
  version: number;
  published_at: string | null;
  is_published: boolean;
}

export interface AgentTemplateDto {
  template_id: string;
  name: string;
  description: string;
  languages: string[];
  persona: PersonaDto;
  providers: ProvidersDto;
  compliance: Record<string, unknown>;
}

export interface ValidationIssueDto {
  code: string;
  message: string;
  field: string | null;
}

export interface ValidationResultDto {
  is_valid: boolean;
  errors: ValidationIssueDto[];
}

export interface AgentVersionDto {
  version: number;
  published_by: string | null;
  published_at: string | null;
}

export type SaveDraftResult =
  | { state: "saved"; agent: AgentDto }
  | { state: "conflict"; message: string }
  | { state: "error"; message: string };

export type PublishDraftResult =
  | { state: "published"; version: number; agent: AgentDto }
  | { state: "conflict"; message: string }
  | { state: "error"; message: string };

export type RestoreVersionResult =
  | { state: "restored"; agent: AgentDto }
  | { state: "conflict"; message: string }
  | { state: "error"; message: string };

export interface AgentEditorActions {
  saveDraft(agentId: string, expectedRevision: number, patch: Partial<AgentDto>): Promise<SaveDraftResult>;
  validateDraft(agentId: string): Promise<ValidationResultDto>;
  publishDraft(agentId: string, expectedRevision: number): Promise<PublishDraftResult>;
  restoreVersion(agentId: string, version: number, expectedRevision: number): Promise<RestoreVersionResult>;
}
