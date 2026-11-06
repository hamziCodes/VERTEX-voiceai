import { createSign, generateKeyPairSync } from "node:crypto";
import { createServer } from "node:http";

const host = "127.0.0.1";
const port = 3211;
const issuer = `http://${host}:${port}/`;
const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const publicJwk = publicKey.export({ format: "jwk" });
const workspaceA = "11111111-1111-4111-8111-111111111111";
const workspaceB = "22222222-2222-4222-8222-222222222222";
const roleCapabilities = {
  tenant_admin: [
    "agent:read", "agent:write", "alert:read", "alert:write", "api_key:read", "api_key:write", "audit:read",
    "conversation:read", "entitlement:read", "extraction:read", "extraction:write", "knowledge:read", "knowledge:write",
    "member:read", "member:write", "onboarding:read", "onboarding:write", "provider_credential:read",
    "provider_credential:write", "secret:rotate", "session:mint", "session:read", "telephony:read", "telephony:write", "usage:read",
  ],
  tenant_editor: [
    "agent:read", "agent:write", "alert:read", "alert:write", "audit:read", "conversation:read", "entitlement:read",
    "extraction:read", "extraction:write", "knowledge:read", "knowledge:write", "member:read", "onboarding:read",
    "onboarding:write", "session:mint", "session:read", "telephony:read", "usage:read",
  ],
  tenant_developer: [
    "agent:read", "api_key:read", "api_key:write", "entitlement:read", "provider_credential:read", "session:mint",
    "session:read", "telephony:read", "usage:read",
  ],
  tenant_viewer: [
    "agent:read", "alert:read", "conversation:read", "entitlement:read", "extraction:read", "knowledge:read",
    "onboarding:read", "session:read", "usage:read",
  ],
  compliance_admin: [
    "audit:read", "compliance:write", "conversation:read", "entitlement:read", "erasure:execute", "legal_hold:manage",
  ],
};
const initialOnboarding = {
  business_name: "Hamzi Stores",
  use_case: "customer_support",
  languages: ["en", "ur"],
  operating_region: "",
  timezone: "Asia/Karachi",
  escalation_email: null,
  completed_steps: ["business", "use_case"],
};
const templateConfig = {
  name: "Retail customer care",
  description: "Order and return support",
  languages: ["en"],
  persona: { system_prompt: "Help customers clearly.", greeting: "Hello, how can I help?", voice_id: "default", voice_by_language: {}, persona_isolation: true },
  providers: { stt: [], llm: [], tts: [], s2s: [] },
  compliance: { tier: "standard", hipaa_baa_acknowledged: false },
};

let onboarding;
let agents;
let versions;
let nextAgent;
let knowledgeBases;
let knowledgeSources;
let nextKnowledgeBase;
let nextKnowledgeSource;
let apiKeys;
let providerCredentials;
let telephonySettings;
let conversations;
let conversationIntelligence;
let usage;
let auditEvents;
let nextApiKey;
let nextProviderCredential;

function resetState() {
  onboarding = new Map([[workspaceA, structuredClone(initialOnboarding)], [workspaceB, structuredClone(initialOnboarding)]]);
  const viewerAgent = { ...structuredClone(templateConfig), name: "Viewer-safe assistant", agent_id: "44444444-4444-4444-8444-444444444444", draft_revision: 1, version: 1, published_at: null, is_published: false };
  agents = new Map([[workspaceA, []], [workspaceB, [viewerAgent]]]);
  versions = new Map();
  nextAgent = 1;
  knowledgeBases = new Map([[workspaceA, []], [workspaceB, []]]);
  knowledgeSources = new Map();
  nextKnowledgeBase = 1;
  nextKnowledgeSource = 1;
  apiKeys = new Map([
    [workspaceA, [{
      key_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      name: "Production Web Client",
      key_prefix: "wavia_live_prod_abc",
      scopes: ["session:mint"],
      role: "tenant_viewer",
      created_at: "2026-10-01T00:00:00Z",
      expires_at: null,
      revoked_at: null,
      last_used_at: "2026-10-30T12:00:00Z",
    }]],
    [workspaceB, []],
  ]);
  providerCredentials = new Map([[workspaceA, []], [workspaceB, []]]);
  const defaultPolicy = {
    outbound_enabled: false,
    allowed_destinations: ["+14155550100"],
    calling_timezone: "UTC",
    window_start: "09:00:00",
    window_end: "17:00:00",
    max_concurrent_calls: 1,
    max_calls_per_minute: 1,
    daily_spend_cap_cents: 100,
    reserved_spend_cents_per_call: 1,
    max_call_duration_seconds: 600,
  };
  const defaultSettings = {
    policy: defaultPolicy,
    readiness: {
      state: "not_configured",
      trunk_configured: false,
      telephony_entitled: false,
      carrier_health: "unknown",
    },
    carrier_actions_allowed: false,
  };
  telephonySettings = new Map([
    [workspaceA, structuredClone(defaultSettings)],
    [workspaceB, structuredClone(defaultSettings)],
  ]);
  const alphaCallId = "91111111-1111-4111-8111-111111111111";
  const alphaConversation = {
    call_id: alphaCallId,
    agent_id: "33333333-3333-4333-8333-000000000001",
    started_at: "2026-11-04T09:00:00Z",
    ended_at: "2026-11-04T09:02:00Z",
    transport_type: "websocket",
    disposition: "completed",
    recording_state: "available",
    turn_count: 2,
    end_reason: "completed",
    transcript: [
      { speaker: "user", text: "I need help with an order", start_ms: 0, end_ms: 900, language: "en", confidence: 0.98 },
      { speaker: "assistant", text: "I can help with that order.", start_ms: 1000, end_ms: 1800, language: "en", confidence: 1 },
    ],
    usage: { stt_sec: 1.8, tts_sec: 0.8, llm_tokens: 22, agent_sec: 2.1 },
    recording: { state: "available", access: "gated", duration_sec: 2 },
  };
  conversations = new Map([[workspaceA, [alphaConversation]], [workspaceB, []]]);
  conversationIntelligence = new Map([[alphaCallId, {
    state: "available",
    result: {
      result_id: "92222222-2222-4222-8222-222222222222",
      call_id: alphaCallId,
      extraction: null,
      summary: { text: "Customer requested help with an order." },
      verification_issue_codes: ["sensitive_field"],
      created_at: "2026-11-04T09:03:00Z",
    },
    review: {
      review_id: "93333333-3333-4333-8333-333333333333",
      call_id: alphaCallId,
      result_id: "92222222-2222-4222-8222-222222222222",
      reasons: ["sensitive_field"],
      state: "pending",
      decided_by: null,
      decision_note: null,
      created_at: "2026-11-04T09:03:00Z",
      decided_at: null,
    },
  }]]);
  usage = new Map([
    [workspaceA, {
      status: "success",
      tenant_id: workspaceA,
      quota: { max_concurrent: 10, max_minutes_month: 1000, max_llm_tokens_month: 100000, current_concurrent: 1, current_monthly_minutes: 12.5, current_monthly_llm_tokens: 2400, soft_cap_percent: 80, hard_cap_percent: 100 },
      totals: { stt_sec: 300, tts_sec: 240, llm_tokens: 2400, agent_sec: 750, telephony_sec: 0 },
    }],
    [workspaceB, {
      status: "success",
      tenant_id: workspaceB,
      quota: { max_concurrent: 2, max_minutes_month: 100, max_llm_tokens_month: 10000, current_concurrent: 0, current_monthly_minutes: 0, current_monthly_llm_tokens: 0, soft_cap_percent: 80, hard_cap_percent: 100 },
      totals: { stt_sec: 0, tts_sec: 0, llm_tokens: 0, agent_sec: 0, telephony_sec: 0 },
    }],
  ]);
  auditEvents = new Map([
    [workspaceA, [{
      id: "94444444-4444-4444-8444-444444444444",
      tenant_id: workspaceA,
      actor_id: "system",
      actor_type: "system",
      action: "provider.degraded",
      resource_type: "provider",
      resource_id: "groq",
      detail: { state: "degraded" },
      ip: null,
      user_agent: null,
      created_at: "2026-11-04T09:04:00Z",
    }]],
    [workspaceB, []],
  ]);
  nextApiKey = 1;
  nextProviderCredential = 1;
}

resetState();

const providerCatalog = [
  { provider_id: "gladia", category: "stt", languages: ["en", "ur"], streaming_input: true, streaming_output: false, supports_tools: false, models: ["default"], readiness: "production" },
  { provider_id: "groq", category: "llm", languages: ["en"], streaming_input: false, streaming_output: true, supports_tools: true, models: ["llama-3.3-70b-versatile"], readiness: "production" },
  { provider_id: "cartesia", category: "tts", languages: ["en"], streaming_input: false, streaming_output: true, supports_tools: false, models: ["sonic-english"], readiness: "production" },
];

function encode(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

function token(subject, expired = false) {
  const now = Math.floor(Date.now() / 1000);
  const header = encode({ alg: "RS256", kid: "offline-test-key", typ: "JWT" });
  const payload = encode({
    sub: subject,
    sid: `session-${subject}`,
    iss: issuer,
    aud: "client_offline_test",
    email: `${subject}@example.test`,
    iat: now - 5,
    exp: expired ? now - 1 : now + 600,
  });
  const input = `${header}.${payload}`;
  const signer = createSign("RSA-SHA256");
  signer.update(input);
  signer.end();
  return `${input}.${signer.sign(privateKey).toString("base64url")}`;
}

function json(response, status, payload) {
  response.writeHead(status, { "content-type": "application/json", "cache-control": "no-store" });
  response.end(JSON.stringify(payload));
}

function subjectFromRequest(request) {
  const raw = request.headers.authorization?.replace(/^Bearer\s+/i, "") ?? "";
  try {
    return JSON.parse(Buffer.from(raw.split(".")[1], "base64url").toString("utf8")).sub;
  } catch {
    return null;
  }
}

function tenantFromRequest(request) {
  return request.headers["x-tenant-id"];
}

async function rawBodyFromRequest(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return Buffer.concat(chunks);
}

async function bodyFromRequest(request) {
  const content = await rawBodyFromRequest(request);
  return content.length ? JSON.parse(content.toString("utf8")) : {};
}

function agentId() {
  const suffix = String(nextAgent++).padStart(12, "0");
  return `33333333-3333-4333-8333-${suffix}`;
}

function findAgent(tenant, id) {
  return (agents.get(tenant) ?? []).find((agent) => agent.agent_id === id);
}

function fixtureId(prefix, value) {
  return `${prefix}${String(value).padStart(7, "0")}-1111-4111-8111-111111111111`;
}

function findKnowledgeBase(tenant, id) {
  return (knowledgeBases.get(tenant) ?? []).find((base) => base.knowledge_base_id === id);
}

function sourcesFor(id) {
  return knowledgeSources.get(id) ?? [];
}

function refreshKnowledgeBase(base) {
  const sources = sourcesFor(base.knowledge_base_id);
  base.source_count = sources.length;
  base.ready_source_count = sources.filter((source) => source.status === "ready").length;
  base.total_chunks = sources.reduce((total, source) => total + source.chunk_count, 0);
  if (base.status !== "active") base.status = sources.length > 0 && base.ready_source_count === sources.length ? "ready" : sources.length > 0 ? "processing" : "draft";
}

function newSource(baseId, displayName, sourceType, mediaType, byteCount) {
  return {
    source_id: fixtureId("6", nextKnowledgeSource++),
    knowledge_base_id: baseId,
    source_type: sourceType,
    display_name: displayName,
    media_type: mediaType,
    byte_count: byteCount,
    revision: 1,
    status: "queued",
    chunk_count: 0,
    error_code: null,
    error_message: null,
  };
}

async function handle(request, response) {
  const url = new URL(request.url ?? "/", issuer);
  if (url.pathname === "/health") return json(response, 200, { ok: true });
  if (url.pathname === "/reset" && request.method === "POST") {
    resetState();
    return json(response, 200, { ok: true });
  }
  if (url.pathname === "/advance-knowledge" && request.method === "POST") {
    for (const [baseId, sources] of knowledgeSources.entries()) {
      for (const source of sources) {
        source.status = "ready";
        source.chunk_count = 1;
      }
      for (const bases of knowledgeBases.values()) {
        const base = bases.find((item) => item.knowledge_base_id === baseId);
        if (base) refreshKnowledgeBase(base);
      }
    }
    return json(response, 200, { ok: true });
  }
  if (url.pathname === "/token") {
    const subject = url.searchParams.get("sub") || "user-two";
    return json(response, 200, { accessToken: token(subject, url.searchParams.get("expired") === "1") });
  }
  if (url.pathname.toLowerCase().includes("jwks")) {
    return json(response, 200, { keys: [{ ...publicJwk, kid: "offline-test-key", alg: "RS256", use: "sig" }] });
  }
  if (url.pathname === "/user_management/sessions/logout") {
    const returnTo = url.searchParams.get("return_to") || "/sign-in";
    response.writeHead(302, { location: new URL(returnTo, "http://127.0.0.1:3100").toString() });
    return response.end();
  }
  if (url.pathname === "/v1/me") {
    const subject = subjectFromRequest(request);
    if (!subject) return json(response, 401, { detail: "Authentication required." });
    const createdAt = "2026-01-01T00:00:00Z";
    const requestedRole = {
      "user-editor": "tenant_editor",
      "user-developer": "tenant_developer",
      "user-viewer": "tenant_viewer",
      "user-compliance": "compliance_admin",
    }[subject] ?? "tenant_admin";
    const memberships = subject === "user-none" ? [] : [
      { user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", tenant_id: workspaceA, tenant_name: "Alpha workspace", role: requestedRole, capabilities: roleCapabilities[requestedRole], created_at: createdAt },
      { user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", tenant_id: workspaceB, tenant_name: "Beta workspace", role: "tenant_viewer", capabilities: roleCapabilities.tenant_viewer, created_at: createdAt },
    ];
    return json(response, 200, {
      user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      email: `${subject}@example.test`,
      is_active: true,
      is_platform_admin: false,
      memberships,
    });
  }
  const tenant = tenantFromRequest(request);
  if (!subjectFromRequest(request)) return json(response, 401, { detail: "Authentication required." });
  if (!tenant || !agents.has(tenant)) return json(response, 403, { detail: "Workspace required." });

  if (url.pathname === "/v1/conversations" && request.method === "GET") {
    const items = (conversations.get(tenant) ?? []).map((item) => ({
      call_id: item.call_id,
      agent_id: item.agent_id,
      started_at: item.started_at,
      ended_at: item.ended_at,
      transport_type: item.transport_type,
      disposition: item.disposition,
      recording_state: item.recording_state,
      turn_count: item.turn_count,
    }));
    return json(response, 200, { items, next_cursor: null });
  }
  const conversationMatch = url.pathname.match(/^\/v1\/conversations\/([0-9a-f-]+)(?:\/(intelligence))?$/i);
  if (conversationMatch && request.method === "GET") {
    const [, callId, tail] = conversationMatch;
    const conversation = (conversations.get(tenant) ?? []).find((item) => item.call_id === callId);
    if (!conversation) return json(response, 404, { detail: "Conversation not found." });
    if (tail === "intelligence") {
      return json(response, 200, conversationIntelligence.get(callId) ?? { state: "unavailable", result: null, review: null });
    }
    return json(response, 200, conversation);
  }
  if (url.pathname === "/v1/usage" && request.method === "GET") {
    return json(response, 200, usage.get(tenant));
  }
  if (url.pathname === "/v1/audit" && request.method === "GET") {
    const events = auditEvents.get(tenant) ?? [];
    return json(response, 200, { status: "success", count: events.length, events });
  }

  if (url.pathname === "/v1/onboarding" && request.method === "GET") {
    const profile = onboarding.get(tenant);
    const requirementCodes = [
      ["business_name_required", profile.business_name],
      ["use_case_required", profile.use_case],
      ["operating_region_required", profile.operating_region],
    ].filter(([, value]) => !value).map(([code]) => code);
    return json(response, 200, { profile, requirement_codes: requirementCodes });
  }
  if (url.pathname === "/v1/onboarding" && request.method === "PATCH") {
    const updated = { ...onboarding.get(tenant), ...await bodyFromRequest(request) };
    onboarding.set(tenant, updated);
    return json(response, 200, { profile: updated, requirement_codes: [] });
  }
  if (url.pathname === "/v1/entitlements" && request.method === "GET") {
    return json(response, 200, { max_agents: 3, max_concurrent_sessions: 2, max_knowledge_bytes: 10485760, api_keys_allowed: 2, telephony_enabled: false, advanced_providers_enabled: false, byok_enabled: false, allowed_retention_days: [7, 30] });
  }
  if (url.pathname === "/v1/agents/templates" && request.method === "GET") {
    return json(response, 200, { templates: [{ template_id: "retail_customer_service", config: templateConfig }] });
  }
  if (url.pathname === "/v1/agents" && request.method === "GET") return json(response, 200, agents.get(tenant));
  if (url.pathname === "/v1/agents" && request.method === "POST") {
    if (agents.get(tenant).length >= 3) return json(response, 409, { detail: "Agent limit reached." });
    const input = await bodyFromRequest(request);
    const created = { ...structuredClone(templateConfig), ...input, agent_id: agentId(), draft_revision: 1, version: 1, published_at: null, is_published: false };
    agents.get(tenant).push(created);
    return json(response, 201, created);
  }
  if (url.pathname === "/v1/studio/sessions" && request.method === "POST") {
    const input = await bodyFromRequest(request);
    const agent = findAgent(tenant, input.agent_id);
    if (!agent?.is_published) return json(response, 409, { detail: "A valid published agent configuration is required." });
    return json(response, 200, {
      status: "success",
      session_id: "offline-session-1",
      token: "offline-ephemeral-room-token",
      ttl_sec: 120,
      ws_url: "ws://offline.worker.test/ws/audio",
      agent_config_version: agent.version,
      session_plan_ref: "offline-plan-1",
    });
  }
  if (url.pathname === "/v1/knowledge-bases" && request.method === "GET") return json(response, 200, knowledgeBases.get(tenant));
  if (url.pathname === "/v1/knowledge-bases" && request.method === "POST") {
    const input = await bodyFromRequest(request);
    const created = { knowledge_base_id: fixtureId("5", nextKnowledgeBase++), name: input.name, status: "draft", active_revision: 0, source_count: 0, ready_source_count: 0, total_chunks: 0 };
    knowledgeBases.get(tenant).push(created);
    knowledgeSources.set(created.knowledge_base_id, []);
    return json(response, 201, created);
  }
  const knowledgeMatch = url.pathname.match(/^\/v1\/knowledge-bases\/([0-9a-f-]+)(.*)$/i);
  if (knowledgeMatch) {
    const [, baseId, tail] = knowledgeMatch;
    const base = findKnowledgeBase(tenant, baseId);
    if (!base) return json(response, 404, { detail: "Knowledge base not found." });
    if (!tail && request.method === "GET") return json(response, 200, base);
    if (tail === "/sources" && request.method === "GET") return json(response, 200, sourcesFor(baseId));
    if (tail === "/sources" && request.method === "POST") {
      const content = await rawBodyFromRequest(request);
      const text = content.toString("utf8");
      const filename = text.match(/filename="([^"]+)"/)?.[1] ?? "upload.txt";
      const source = newSource(baseId, filename, filename.toLowerCase().endsWith(".txt") ? "txt" : "document", request.headers["content-type"] ?? "application/octet-stream", content.length);
      sourcesFor(baseId).push(source);
      refreshKnowledgeBase(base);
      return json(response, 202, source);
    }
    if (tail === "/faqs" && request.method === "POST") {
      const input = await bodyFromRequest(request);
      const source = newSource(baseId, `${input.name}.json`, "faq", "application/json", JSON.stringify(input.items).length);
      sourcesFor(baseId).push(source);
      refreshKnowledgeBase(base);
      return json(response, 202, source);
    }
    if (tail === "/preview-query" && request.method === "POST") {
      const input = await bodyFromRequest(request);
      return json(response, 200, { knowledge_base_id: baseId, revision: base.active_revision || 1, query: input.query, results: [{ source_id: sourcesFor(baseId)[0]?.source_id, revision: 1, ordinal: 1, text: "Refunds are available within 30 days.", citation: { heading: "Refund policy", line_start: 1 }, score: 0.91 }] });
    }
    if (tail === "/activate" && request.method === "POST") {
      const sources = sourcesFor(baseId);
      if (sources.length === 0 || sources.some((source) => source.status !== "ready")) return json(response, 409, { detail: "Knowledge is not ready." });
      Object.assign(base, { status: "active", active_revision: base.active_revision + 1 });
      refreshKnowledgeBase(base);
      return json(response, 200, base);
    }
    const sourceMatch = tail.match(/^\/sources\/([0-9a-f-]+)(?:\/(retry))?$/i);
    if (sourceMatch) {
      const sourceId = sourceMatch[1];
      const source = sourcesFor(baseId).find((item) => item.source_id === sourceId);
      if (!source) return json(response, 404, { detail: "Source not found." });
      if (sourceMatch[2] === "retry" && request.method === "POST") {
        Object.assign(source, { status: "queued", error_code: null, error_message: null });
        return json(response, 200, { job_id: fixtureId("7", 1), source_id: sourceId, status: "queued", attempt: 2 });
      }
      if (!sourceMatch[2] && request.method === "DELETE") {
        knowledgeSources.set(baseId, sourcesFor(baseId).filter((item) => item.source_id !== sourceId));
        refreshKnowledgeBase(base);
        response.writeHead(204);
        return response.end();
      }
    }
    const bindMatch = tail.match(/^\/bind\/([0-9a-f-]+)$/i);
    if (bindMatch && request.method === "POST") {
      const agent = findAgent(tenant, bindMatch[1]);
      if (!agent) return json(response, 404, { detail: "Agent not found." });
      return json(response, 200, { binding_id: fixtureId("8", 1), agent_id: agent.agent_id, agent_config_version: 1, knowledge_base_id: baseId, knowledge_revision: base.active_revision });
    }
  }
  const match = url.pathname.match(/^\/v1\/agents\/([0-9a-f-]+)(.*)$/i);
  if (match) {
    const [, id, tail] = match;
    const agent = findAgent(tenant, id);
    if (!agent) return json(response, 404, { detail: "Agent not found." });
    if (!tail && request.method === "GET") return json(response, 200, agent);
    if (tail === "/autosave" && request.method === "PATCH") {
      const input = await bodyFromRequest(request);
      if (input.expected_revision !== agent.draft_revision) return json(response, 409, { detail: "A newer draft exists." });
      Object.assign(agent, input.patch, { draft_revision: agent.draft_revision + 1, is_published: false });
      return json(response, 200, { saved: true, agent });
    }
    if (tail === "/validate" && request.method === "POST") return json(response, 200, { is_valid: true, errors: [] });
    if (tail === "/publish" && request.method === "POST") {
      const input = await bodyFromRequest(request);
      if (input.expected_revision !== agent.draft_revision) return json(response, 409, { detail: "A newer draft exists." });
      const version = (versions.get(id)?.length ?? 0) + 1;
      Object.assign(agent, { version, published_at: "2026-10-30T12:00:00Z", is_published: true, draft_revision: agent.draft_revision + 1 });
      const history = versions.get(id) ?? [];
      history.push({ version, published_by: "offline-user", published_at: agent.published_at, snapshot: structuredClone(agent) });
      versions.set(id, history);
      return json(response, 200, { version, published_at: agent.published_at, config: agent });
    }
    if (tail === "/versions" && request.method === "GET") {
      return json(response, 200, (versions.get(id) ?? []).map((item) => ({ version: item.version, published_by: item.published_by, published_at: item.published_at })));
    }
    const restoreMatch = tail.match(/^\/versions\/(\d+)\/restore$/);
    if (restoreMatch && request.method === "POST") {
      const input = await bodyFromRequest(request);
      if (input.expected_revision !== agent.draft_revision) return json(response, 409, { detail: "A newer draft exists." });
      const stored = (versions.get(id) ?? []).find((item) => item.version === Number(restoreMatch[1]));
      if (!stored) return json(response, 404, { detail: "Version not found." });
      const revision = agent.draft_revision + 1;
      Object.assign(agent, structuredClone(stored.snapshot), { draft_revision: revision, is_published: false, published_at: null });
      return json(response, 200, agent);
    }
  }

  // ── API Keys ──────────────────────────────────────────────────────────────
  if (url.pathname === "/v1/api-keys" && request.method === "GET") {
    return json(response, 200, { keys: apiKeys.get(tenant) ?? [] });
  }
  if (url.pathname === "/v1/api-keys" && request.method === "POST") {
    const input = await bodyFromRequest(request);
    const id = fixtureId("a", nextApiKey++);
    const created = {
      key_id: id,
      name: input.name ?? "New Key",
      key_prefix: `wavia_live_${String(nextApiKey).padStart(4, "0")}`,
      role: input.role ?? "tenant_viewer",
      scopes: input.scopes ?? ["session:mint"],
      created_at: new Date().toISOString(),
      expires_at: input.expires_at ?? null,
      revoked_at: null,
      last_used_at: null,
    };
    (apiKeys.get(tenant) ?? []).push(created);
    return json(response, 201, {
      api_key: "wavia_live_secret_plaintext_key_123456",
      key: created,
    });
  }
  const apiKeyMatch = url.pathname.match(/^\/v1\/api-keys\/([^/]+)$/i);
  if (apiKeyMatch && request.method === "DELETE") {
    const id = apiKeyMatch[1];
    apiKeys.set(tenant, (apiKeys.get(tenant) ?? []).filter((k) => k.key_id !== id));
    response.writeHead(204); return response.end();
  }

  // ── Provider Catalog ──────────────────────────────────────────────────────
  if (url.pathname === "/v1/catalog/providers" && request.method === "GET") {
    return json(response, 200, { providers: providerCatalog });
  }

  // ── Provider Credentials ──────────────────────────────────────────────────
  if (url.pathname === "/v1/provider-credentials" && request.method === "GET") {
    return json(response, 200, { credentials: providerCredentials.get(tenant) ?? [] });
  }
  if (url.pathname === "/v1/provider-credentials" && request.method === "POST") {
    const input = await bodyFromRequest(request);
    const id = String(nextProviderCredential++).padStart(64, "c");
    const cred = {
      credential_id: id,
      provider_id: input.provider_id,
      credential_type: input.credential_type ?? "api_key",
      reference: input.reference ?? "default",
      rotation_version: 1,
      status: "active",
      created_at: new Date().toISOString(),
      rotated_at: null,
    };
    (providerCredentials.get(tenant) ?? []).push(cred);
    return json(response, 201, cred);
  }
  const credMatch = url.pathname.match(/^\/v1\/provider-credentials\/([^/]+)$/i);
  if (credMatch && request.method === "DELETE") {
    const id = credMatch[1];
    providerCredentials.set(tenant, (providerCredentials.get(tenant) ?? []).filter((c) => c.credential_id !== id));
    response.writeHead(204); return response.end();
  }

  // ── Telephony Settings ────────────────────────────────────────────────────
  if (url.pathname === "/v1/telephony/settings" && request.method === "GET") {
    return json(response, 200, telephonySettings.get(tenant));
  }
  if (url.pathname === "/v1/telephony/settings" && request.method === "PUT") {
    const input = await bodyFromRequest(request);
    const current = telephonySettings.get(tenant);
    telephonySettings.set(tenant, { ...current, policy: { ...current.policy, ...input } });
    return json(response, 200, telephonySettings.get(tenant));
  }

    return json(response, 404, { detail: "Offline fixture route not found." });
}

const server = createServer((request, response) => {
  void handle(request, response).catch(() => json(response, 500, { detail: "Offline fixture failure." }));
}).listen(port, host);

function shutdown() {
  server.closeAllConnections?.();
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 500).unref();
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
