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

export const voiceSessionSchema = z.object({
  status: z.literal("success"),
  session_id: z.string().min(1),
  token: z.string().min(1),
  ttl_sec: z.number().int().positive(),
  ws_url: z.string().url(),
  agent_config_version: z.number().int().positive(),
  session_plan_ref: z.string().min(1),
});

export const apiKeySchema = z.object({
  key_id: z.string().uuid(),
  name: z.string().min(1),
  key_prefix: z.string(),
  scopes: z.array(z.string()),
  role: z.string(),
  created_at: z.string().nullable(),
  expires_at: z.string().nullable(),
  revoked_at: z.string().nullable(),
  last_used_at: z.string().nullable(),
});
export type APIKeyDto = z.infer<typeof apiKeySchema>;

export const apiKeyListSchema = z.object({
  keys: z.array(apiKeySchema),
});
export type APIKeyListDto = z.infer<typeof apiKeyListSchema>;

export const createApiKeyResponseSchema = z.object({
  api_key: z.string().min(1),
  key: apiKeySchema,
});
export type CreateApiKeyResponseDto = z.infer<typeof createApiKeyResponseSchema>;

export const providerCredentialSchema = z.object({
  credential_id: z.string().min(1),
  provider_id: z.string().min(1),
  credential_type: z.string(),
  reference: z.string(),
  rotation_version: z.number().int().nonnegative(),
  status: z.string(),
  created_at: z.string().nullable(),
  rotated_at: z.string().nullable(),
});
export type ProviderCredentialDto = z.infer<typeof providerCredentialSchema>;

export const providerCredentialListSchema = z.object({
  credentials: z.array(providerCredentialSchema),
});
export type ProviderCredentialListDto = z.infer<typeof providerCredentialListSchema>;

export const catalogProviderSchema = z.object({
  provider_id: z.string().min(1),
  category: z.string(),
  languages: z.array(z.string()),
  streaming_input: z.boolean(),
  streaming_output: z.boolean(),
  supports_tools: z.boolean(),
  models: z.array(z.string()),
  readiness: z.string(),
});
export type CatalogProviderDto = z.infer<typeof catalogProviderSchema>;

export const catalogProviderListSchema = z.object({
  providers: z.array(catalogProviderSchema),
});
export type CatalogProviderListDto = z.infer<typeof catalogProviderListSchema>;

export const telephonyPolicySchema = z.object({
  outbound_enabled: z.boolean().default(false),
  allowed_destinations: z.array(z.string()).default([]),
  calling_timezone: z.string().default("UTC"),
  window_start: z.string().default("09:00:00"),
  window_end: z.string().default("17:00:00"),
  max_concurrent_calls: z.number().int().positive().default(1),
  max_calls_per_minute: z.number().int().positive().default(1),
  daily_spend_cap_cents: z.number().int().positive().default(100),
  reserved_spend_cents_per_call: z.number().int().positive().default(1),
  max_call_duration_seconds: z.number().int().positive().default(600),
});
export type TelephonyPolicyDto = z.infer<typeof telephonyPolicySchema>;

export const telephonyReadinessSchema = z.object({
  state: z.string(),
  trunk_configured: z.boolean(),
  telephony_entitled: z.boolean(),
  carrier_health: z.string(),
});
export type TelephonyReadinessDto = z.infer<typeof telephonyReadinessSchema>;

export const telephonySettingsSchema = z.object({
  policy: telephonyPolicySchema,
  readiness: telephonyReadinessSchema,
  carrier_actions_allowed: z.boolean(),
});
export type TelephonySettingsDto = z.infer<typeof telephonySettingsSchema>;

export function parseControlPlaneDto<T>(
  schema: z.ZodType<T>,
  payload: unknown,
): T {
  return schema.parse(payload);
}
