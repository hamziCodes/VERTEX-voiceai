import { z } from "zod";

export const workspaceSummarySchema = z.object({
  user_id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  tenant_name: z.string().trim().min(1),
  role: z.enum(["tenant_admin", "tenant_editor", "tenant_viewer", "compliance_admin"]),
  created_at: z.iso.datetime(),
});

export const currentIdentitySchema = z.object({
  user_id: z.string().uuid(),
  email: z.string().email().nullable(),
  is_active: z.boolean(),
  is_platform_admin: z.boolean(),
  memberships: z.array(workspaceSummarySchema),
});

export const onboardingProfileSchema = z.object({
  business_name: z.string(),
  use_case: z.string(),
  languages: z.array(z.string()),
  operating_region: z.string(),
  timezone: z.string(),
  escalation_email: z.string().nullable(),
  completed_steps: z.array(z.string()),
});

export const onboardingResponseSchema = z.object({
  profile: onboardingProfileSchema,
  requirement_codes: z.array(z.string()),
});

export const entitlementsSchema = z.object({
  max_agents: z.number().int().positive(),
  max_concurrent_sessions: z.number().int().positive(),
  max_knowledge_bytes: z.number().int().nonnegative(),
  api_keys_allowed: z.number().int().nonnegative(),
  telephony_enabled: z.boolean(),
  advanced_providers_enabled: z.boolean(),
  byok_enabled: z.boolean(),
  allowed_retention_days: z.array(z.number().int().positive()),
});

const providerRouteSchema = z.object({
  provider_id: z.string().min(1),
  model: z.string().nullable().optional(),
  enabled: z.boolean(),
  priority: z.number().int(),
});

const providerChainSchema = z.object({
  category: z.string().min(1),
  language: z.string().min(1),
  routes: z.array(providerRouteSchema),
});

const providersSchema = z.object({
  stt: z.array(providerChainSchema),
  llm: z.array(providerChainSchema),
  tts: z.array(providerChainSchema),
  s2s: z.array(providerChainSchema),
});

const personaSchema = z.object({
  system_prompt: z.string(),
  greeting: z.string().nullable(),
  voice_id: z.string(),
  voice_by_language: z.record(z.string(), z.string()).default({}),
  persona_isolation: z.boolean(),
});

export const agentSchema = z.object({
  agent_id: z.string().uuid(),
  name: z.string().min(1),
  description: z.string(),
  languages: z.array(z.string()),
  persona: personaSchema,
  providers: providersSchema,
  compliance: z.record(z.string(), z.unknown()),
  draft_revision: z.number().int().positive(),
  version: z.number().int().positive(),
  published_at: z.string().nullable(),
  is_published: z.boolean(),
});

export const agentListSchema = z.array(agentSchema);

export const templateResponseSchema = z.object({
  templates: z.array(z.object({
    template_id: z.string().min(1),
    config: z.object({
      name: z.string().min(1),
      description: z.string(),
      languages: z.array(z.string()),
      persona: personaSchema,
      providers: providersSchema,
      compliance: z.record(z.string(), z.unknown()),
    }),
  })),
});

export const validationResultSchema = z.object({
  is_valid: z.boolean(),
  errors: z.array(z.object({
    code: z.string(),
    message: z.string(),
    field: z.string().nullable(),
  })),
});

export const autosaveResponseSchema = z.object({ saved: z.boolean(), agent: agentSchema });
export const publishResponseSchema = z.object({ version: z.number().int().positive(), config: agentSchema });
export const agentVersionsSchema = z.array(z.object({
  version: z.number().int().positive(),
  published_by: z.string().nullable(),
  published_at: z.string().nullable(),
}));

export const knowledgeBaseSchema = z.object({
  knowledge_base_id: z.string().uuid(),
  name: z.string().min(1),
  status: z.enum(["draft", "processing", "ready", "active", "failed", "deleting"]),
  active_revision: z.number().int().nonnegative(),
  source_count: z.number().int().nonnegative(),
  ready_source_count: z.number().int().nonnegative(),
  total_chunks: z.number().int().nonnegative(),
});

export const knowledgeBaseListSchema = z.array(knowledgeBaseSchema);

export const knowledgeSourceSchema = z.object({
  source_id: z.string().uuid(),
  knowledge_base_id: z.string().uuid(),
  source_type: z.string(),
  display_name: z.string().min(1),
  media_type: z.string(),
  byte_count: z.number().int().nonnegative(),
  revision: z.number().int().positive(),
  status: z.enum(["uploaded", "queued", "parsing", "chunking", "embedding", "ready", "failed", "deleting"]),
  chunk_count: z.number().int().nonnegative(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
});

export const knowledgeSourceListSchema = z.array(knowledgeSourceSchema);

export const knowledgePreviewSchema = z.object({
  results: z.array(z.object({
    source_id: z.string().uuid(),
    text: z.string(),
    citation: z.record(z.string(), z.unknown()),
    score: z.number().nullable(),
  })),
});

export const knowledgeRetrySchema = z.object({
  source_id: z.string().uuid(),
  status: z.literal("queued"),
});

export const knowledgeBindingSchema = z.object({
  agent_config_version: z.number().int().positive(),
  knowledge_revision: z.number().int().positive(),
});

export function parseControlPlaneDto<T>(
  schema: z.ZodType<T>,
  payload: unknown,
): T {
  return schema.parse(payload);
}
