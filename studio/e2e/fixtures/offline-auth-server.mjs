import { createHash, createSign, generateKeyPairSync, randomBytes } from "node:crypto";
import { createServer } from "node:http";

const host = "127.0.0.1";
const port = Number(process.env.WAVIA_E2E_FIXTURE_PORT ?? "3211");
const appPort = Number(process.env.WAVIA_E2E_APP_PORT ?? "3100");
const issuer = `http://${host}:${port}/`;
const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const publicJwk = publicKey.export({ format: "jwk" });
// Key ID tied to this process's key, so a restarted double never reuses a cached key.
const signingKeyId = `offline-${createHash("sha256").update(publicJwk.n).digest("hex").slice(0, 16)}`;
const workspaceA = "11111111-1111-4111-8111-111111111111";
const workspaceB = "22222222-2222-4222-8222-222222222222";
const roleCapabilities = {
  tenant_admin: [
    "agent:read", "agent:write", "alert:read", "alert:write", "api_key:read", "api_key:write", "audit:read",
    "conversation:read", "entitlement:read", "extraction:read", "extraction:write", "knowledge:read", "knowledge:write",
    "member:read", "member:write", "onboarding:read", "onboarding:write", "provider_credential:read",
    "provider_credential:write", "secret:rotate", "session:mint", "session:read", "telephony:read", "telephony:write", "usage:read",
    "webhook:read", "webhook:write",
  ],
  tenant_editor: [
    "agent:read", "agent:write", "alert:read", "alert:write", "audit:read", "conversation:read", "entitlement:read",
    "extraction:read", "extraction:write", "knowledge:read", "knowledge:write", "member:read", "onboarding:read",
    "onboarding:write", "session:mint", "session:read", "telephony:read", "usage:read",
  ],
  tenant_developer: [
    "agent:read", "api_key:read", "api_key:write", "entitlement:read", "provider_credential:read", "session:mint",
    "session:read", "telephony:read", "usage:read", "webhook:read", "webhook:write",
  ],
  tenant_viewer: [
    "agent:read", "alert:read", "conversation:read", "entitlement:read", "extraction:read", "knowledge:read",
    "onboarding:read", "session:read", "usage:read",
  ],
  compliance_admin: [
    "audit:read", "compliance:write", "conversation:read", "entitlement:read", "erasure:execute", "legal_hold:manage",
  ],
};
const DEFAULT_USER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const subjectUsers = {
  "user-editor": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  "user-viewer": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  "user-developer": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  "user-compliance": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
  // Only joins a workspace by accepting an invitation in the member journey.
  "user-new": "ffffffff-ffff-4fff-8fff-ffffffffffff",
  // Phase 13J Wavia staff: no customer workspace membership at all.
  "user-platform-admin": "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1",
  "user-platform-support": "b2b2b2b2-b2b2-4b2b-8b2b-b2b2b2b2b2b2",
};
// Mirrors control_plane/auth/platform_rbac.py; no wildcard.
const platformCapabilities = {
  platform_admin: [
    "platform_audit:read", "platform_operations:read", "platform_staff:read", "platform_staff:write",
    "platform_support_session:manage", "platform_support_session:read", "platform_support_session:write", "platform_tenant:read",
  ],
  platform_support: ["platform_support_session:read", "platform_support_session:write", "platform_tenant:read"],
};
const supportScopes = ["configuration", "readiness"];
const platformRoles = new Set(Object.keys(platformCapabilities));
const PLATFORM_SUBJECTS = new Set(["user-platform-admin", "user-platform-support"]);
// Directory-only tenants so the bounded directory has a second page (25 per page).
const directoryOnlyTenants = Array.from({ length: 26 }, (_, index) => ({
  tenant_id: `c0000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
  name: `Fixture tenant ${String(index + 1).padStart(2, "0")}`,
  created_at: "2026-02-01T00:00:00Z",
}));
const launchRoles = new Set(Object.keys(roleCapabilities));
const membershipCreatedAt = "2026-01-01T00:00:00Z";
const workspaceNames = new Map([[workspaceA, "Alpha workspace"], [workspaceB, "Beta workspace"]]);
// Labelled offline fixture value only; never a real invitation.
const expiredInvitationToken = "offline_expired_invitation_token_0001";
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
let members;
let invitations;
let nextInvitation;
let platformStaff;
let platformAudit;
let nextPlatformEvent;
let supportSessions;
let nextSupportSession;

const webhookTargets = new Map();

function resetState() {
  webhookTargets.clear();
  platformStaff = new Map([
    [subjectUsers["user-platform-admin"], { role: "platform_admin", granted_by: null, granted_at: "2026-01-01T00:00:00Z", reason: "Initial operator bootstrap" }],
    [subjectUsers["user-platform-support"], { role: "platform_support", granted_by: subjectUsers["user-platform-admin"], granted_at: "2026-01-02T00:00:00Z", reason: "Support rota for launch" }],
  ]);
  platformAudit = [];
  nextPlatformEvent = 1;
  supportSessions = new Map();
  nextSupportSession = 1;
  members = new Map([
    [workspaceA, new Map([
      [DEFAULT_USER_ID, "tenant_admin"],
      [subjectUsers["user-editor"], "tenant_editor"],
      [subjectUsers["user-viewer"], "tenant_viewer"],
      [subjectUsers["user-developer"], "tenant_developer"],
      [subjectUsers["user-compliance"], "compliance_admin"],
    ])],
    [workspaceB, new Map([
      [DEFAULT_USER_ID, "tenant_viewer"],
      [subjectUsers["user-editor"], "tenant_viewer"],
      [subjectUsers["user-viewer"], "tenant_viewer"],
      [subjectUsers["user-developer"], "tenant_viewer"],
      [subjectUsers["user-compliance"], "tenant_viewer"],
    ])],
  ]);
  invitations = new Map([[expiredInvitationToken, {
    invitation_id: "f0000000-1111-4111-8111-111111111111",
    tenant_id: workspaceA,
    email: "user-new@example.test",
    role: "tenant_viewer",
    invited_by: DEFAULT_USER_ID,
    expires_at: "2026-01-02T00:00:00Z",
    accepted_at: null,
    accepted_by: null,
    created_at: "2026-01-01T00:00:00Z",
  }]]);
  nextInvitation = 1;
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
      summary: { executive_summary: "Customer requested help with an order.", key_takeaways: [], sentiment_trajectory: [], source_turn_ids: [0], provider_id: "groq", model_id: "openai/gpt-oss-120b" },
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

// Hosted-sign-in double (customer-journey checkup): authorization codes and
// refresh tokens issued by /user_management/authorize for real browser
// sign-in through Studio's own AuthKit callback.
const authCodes = new Map();
const refreshTokens = new Map();

function identityFor(email) {
  const normalized = email.trim().toLowerCase();
  const id = `user_${createHash("sha256").update(normalized).digest("hex").slice(0, 20)}`;
  const [local] = normalized.split("@");
  return { id, email: normalized, firstName: local.charAt(0).toUpperCase() + local.slice(1), lastName: "Customer" };
}

function workosUser(identity) {
  const now = new Date().toISOString();
  return {
    object: "user", id: identity.id, email: identity.email, email_verified: true,
    first_name: identity.firstName, last_name: identity.lastName,
    profile_picture_url: null, created_at: now, updated_at: now, last_sign_in_at: now, metadata: {},
  };
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function token(subject, expired = false, email = `${subject}@example.test`) {
  const now = Math.floor(Date.now() / 1000);
  const header = encode({ alg: "RS256", kid: signingKeyId, typ: "JWT" });
  const payload = encode({
    sub: subject,
    sid: `session-${subject}`,
    iss: issuer,
    aud: "client_offline_test",
    email,
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

function userIdForSubject(subject) {
  return subjectUsers[subject] ?? DEFAULT_USER_ID;
}

function membershipDto(tenantId, userId, role) {
  return { user_id: userId, tenant_id: tenantId, tenant_name: workspaceNames.get(tenantId), role, created_at: membershipCreatedAt };
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

// ── Platform staff API (mirrors control_plane/routes/platform.py) ──────────
function entitlementsDto() {
  return { max_agents: 3, max_concurrent_sessions: 2, max_knowledge_bytes: 10485760, api_keys_allowed: 2, telephony_enabled: false, advanced_providers_enabled: false, byok_enabled: false, allowed_retention_days: [7, 30] };
}

function emailForUser(userId) {
  const subject = Object.entries(subjectUsers).find(([, id]) => id === userId)?.[0] ?? (userId === DEFAULT_USER_ID ? "user-two" : null);
  return subject ? `${subject}@example.test` : null;
}

function userForEmail(email) {
  if (email === "user-two@example.test") return DEFAULT_USER_ID;
  const subject = email.endsWith("@example.test") ? email.slice(0, -"@example.test".length) : null;
  return subject ? subjectUsers[subject] ?? null : null;
}

function platformDirectory() {
  const workspaces = [...workspaceNames].map(([tenant_id, name]) => ({ tenant_id, name, created_at: membershipCreatedAt }));
  return [...workspaces, ...directoryOnlyTenants].sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()) || a.tenant_id.localeCompare(b.tenant_id));
}

function directoryEntry(tenant) {
  const tenantMembers = members.get(tenant.tenant_id);
  return { ...tenant, member_count: tenantMembers ? tenantMembers.size : 0, agent_count: agents.get(tenant.tenant_id)?.length ?? 0 };
}

function staffDto(userId) {
  const assignment = platformStaff.get(userId);
  return { user_id: userId, email: emailForUser(userId), ...assignment };
}

function recordPlatformEvent(event) {
  platformAudit.unshift({
    event_id: `d0000000-0000-4000-8000-${String(nextPlatformEvent++).padStart(12, "0")}`,
    actor_user_id: null, target_user_id: null, target_tenant_id: null,
    previous_role: null, new_role: null, reason: null,
    created_at: new Date().toISOString(),
    support_session_id: null, scope: null,
    ...event,
  });
}

function supportDto(item) {
  const state = item.ended_at ? "ended" : Date.parse(item.expires_at) <= Date.now() ? "expired" : "active";
  return { ...item, actor_email: emailForUser(item.actor_user_id), state };
}

function supportAgentDto(agent) {
  const providers = agent.providers ?? {};
  return {
    agent_id: agent.agent_id,
    name: agent.name,
    description: agent.description ?? "",
    languages: agent.languages ?? [],
    version: agent.version ?? 1,
    draft_revision: agent.draft_revision ?? 1,
    is_published: Boolean(agent.is_published),
    published_at: agent.published_at ?? null,
    provider_route_counts: Object.fromEntries(["stt", "llm", "tts", "s2s"].map((stage) => [stage, (providers[stage] ?? []).length])),
    knowledge_base_count: (agent.knowledge_bases ?? []).length,
    tool_count: (agent.tools ?? []).length,
    mcp_server_count: (agent.mcp_servers ?? []).length,
    telephony_configured: Boolean(agent.telephony),
    compliance_tier: agent.compliance?.tier ?? "standard",
  };
}

function validReason(value) {
  const reason = String(value ?? "").split(/\s+/).filter(Boolean).join(" ");
  return reason.length >= 8 && reason.length <= 500 ? reason : null;
}

async function handlePlatform(request, response, url) {
  const subject = subjectFromRequest(request);
  if (!subject) return json(response, 401, { detail: "Authentication required." });
  if (request.headers["x-tenant-id"] !== undefined || request.headers["x-actor-role"] !== undefined) {
    return json(response, 400, { detail: "Platform routes do not accept tenant or role context." });
  }
  const actorId = userIdForSubject(subject);
  const role = platformStaff.get(actorId)?.role;
  if (!role) return json(response, 403, { detail: "Platform staff role is required." });
  const can = (permission) => platformCapabilities[role].includes(permission);
  const deny = () => json(response, 403, { detail: "Permission denied." });
  const path = url.pathname.slice("/v1/platform".length);

  if (path === "/me" && request.method === "GET") {
    return json(response, 200, { user_id: actorId, email: `${subject}@example.test`, role, capabilities: platformCapabilities[role] });
  }
  if (path === "/tenants" && request.method === "GET") {
    if (!can("platform_tenant:read")) return deny();
    const limit = Number(url.searchParams.get("limit") ?? 25);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const q = (url.searchParams.get("q") ?? "").trim();
    if (!Number.isInteger(limit) || limit < 1 || limit > 50 || !Number.isInteger(offset) || offset < 0 || offset > 10000 || q.length > 255) {
      return json(response, 422, { detail: "Invalid directory window." });
    }
    const needle = q.toLowerCase();
    const matches = platformDirectory().filter((tenant) => !needle || tenant.tenant_id === needle || tenant.name.toLowerCase().includes(needle));
    return json(response, 200, { items: matches.slice(offset, offset + limit).map(directoryEntry), total: matches.length, limit, offset });
  }
  const tenantMatch = path.match(/^\/tenants\/([^/]+)$/);
  if (tenantMatch && request.method === "GET") {
    if (!can("platform_tenant:read")) return deny();
    const tenant = platformDirectory().find((item) => item.tenant_id === tenantMatch[1]);
    if (!tenant) return json(response, 404, { detail: "Workspace was not found." });
    const counts = {};
    for (const memberRole of members.get(tenant.tenant_id)?.values() ?? []) counts[memberRole] = (counts[memberRole] ?? 0) + 1;
    recordPlatformEvent({ action: "platform_tenant.viewed", actor_user_id: actorId, target_tenant_id: tenant.tenant_id });
    const workspace = workspaceNames.has(tenant.tenant_id);
    return json(response, 200, {
      tenant_id: tenant.tenant_id,
      name: tenant.name,
      created_at: tenant.created_at,
      members_by_role: Object.fromEntries(Object.entries(counts).sort()),
      agent_count: agents.get(tenant.tenant_id)?.length ?? 0,
      entitlements: workspace ? entitlementsDto() : null,
      onboarding_completed_steps: onboarding.get(tenant.tenant_id)?.completed_steps ?? [],
    });
  }
  if (path === "/staff" && request.method === "GET") {
    if (!can("platform_staff:read")) return deny();
    const staff = [...platformStaff.keys()].map(staffDto).sort((a, b) => a.role.localeCompare(b.role) || String(a.email).localeCompare(String(b.email)));
    return json(response, 200, staff);
  }
  if (path === "/staff" && request.method === "PUT") {
    if (!can("platform_staff:write")) return deny();
    const input = await bodyFromRequest(request);
    const reason = validReason(input.reason);
    const email = String(input.email ?? "").trim().toLowerCase();
    if (!reason || !platformRoles.has(input.role) || email.length < 3) return json(response, 422, { detail: "Invalid staff grant." });
    const targetId = userForEmail(email);
    if (!targetId) return json(response, 404, { detail: "No active Wavia user has that email." });
    const previous = platformStaff.get(targetId)?.role ?? null;
    if (previous !== input.role) {
      const admins = [...platformStaff.values()].filter((item) => item.role === "platform_admin").length;
      if (previous === "platform_admin" && admins <= 1) return json(response, 409, { detail: "Wavia must retain one platform administrator." });
      platformStaff.set(targetId, { role: input.role, granted_by: actorId, granted_at: new Date().toISOString(), reason });
      recordPlatformEvent({
        action: previous ? "platform_staff.role_changed" : "platform_staff.granted",
        actor_user_id: actorId, target_user_id: targetId, previous_role: previous, new_role: input.role, reason,
      });
    }
    return json(response, 200, staffDto(targetId));
  }
  const revokeMatch = path.match(/^\/staff\/([^/]+)\/revoke$/);
  if (revokeMatch && request.method === "POST") {
    if (!can("platform_staff:write")) return deny();
    const input = await bodyFromRequest(request);
    const reason = validReason(input.reason);
    if (!reason) return json(response, 422, { detail: "Invalid revocation." });
    const target = platformStaff.get(revokeMatch[1]);
    if (!target) return json(response, 404, { detail: "Platform staff assignment was not found." });
    const admins = [...platformStaff.values()].filter((item) => item.role === "platform_admin").length;
    if (target.role === "platform_admin" && admins <= 1) return json(response, 409, { detail: "Wavia must retain one platform administrator." });
    platformStaff.delete(revokeMatch[1]);
    recordPlatformEvent({ action: "platform_staff.revoked", actor_user_id: actorId, target_user_id: revokeMatch[1], previous_role: target.role, reason });
    response.writeHead(204, { "cache-control": "no-store" });
    return response.end();
  }
  const startMatch = path.match(/^\/tenants\/([^/]+)\/support-sessions$/);
  if (startMatch && request.method === "POST") {
    if (!can("platform_support_session:write")) return deny();
    const input = await bodyFromRequest(request);
    const reason = validReason(input.reason);
    const scopes = Array.isArray(input.scopes) ? supportScopes.filter((scope) => input.scopes.includes(scope)) : [];
    const invalidScope = !Array.isArray(input.scopes) || input.scopes.some((scope) => !supportScopes.includes(scope));
    const reference = input.reference == null ? null : String(input.reference).trim() || null;
    if (!reason || invalidScope || scopes.length === 0 || ![15, 30, 60].includes(input.duration_minutes) || (reference && reference.length > 64)) {
      return json(response, 422, { detail: "Invalid support session." });
    }
    const tenant = platformDirectory().find((item) => item.tenant_id === startMatch[1]);
    if (!tenant) return json(response, 404, { detail: "Workspace was not found." });
    const open = [...supportSessions.values()].some((item) => item.actor_user_id === actorId && item.tenant_id === tenant.tenant_id && supportDto(item).state === "active");
    if (open) return json(response, 409, { detail: "You already have an active support session for this tenant." });
    const created = new Date();
    const item = {
      session_id: `e0000000-0000-4000-8000-${String(nextSupportSession++).padStart(12, "0")}`,
      actor_user_id: actorId,
      tenant_id: tenant.tenant_id,
      tenant_name: tenant.name,
      reason,
      reference,
      scopes,
      created_at: created.toISOString(),
      expires_at: new Date(created.getTime() + input.duration_minutes * 60_000).toISOString(),
      ended_at: null,
      ended_by: null,
      end_reason: null,
    };
    supportSessions.set(item.session_id, item);
    recordPlatformEvent({ action: "platform_support.session_started", actor_user_id: actorId, target_tenant_id: tenant.tenant_id, reason, support_session_id: item.session_id });
    return json(response, 201, supportDto(item));
  }
  if (path === "/support-sessions" && request.method === "GET") {
    if (!can("platform_support_session:read")) return deny();
    const state = url.searchParams.get("state") ?? "recent";
    if (!["active", "recent"].includes(state)) return json(response, 422, { detail: "Invalid state." });
    const items = [...supportSessions.values()].map(supportDto).reverse();
    return json(response, 200, state === "active" ? items.filter((item) => item.state === "active") : items);
  }
  const supportMatch = path.match(/^\/support-sessions\/([^/]+)(?:\/(end|configuration|readiness))?$/);
  if (supportMatch) {
    const [, sessionId, action] = supportMatch;
    const item = supportSessions.get(sessionId);
    if (!action && request.method === "GET") {
      if (!can("platform_support_session:read")) return deny();
      return item ? json(response, 200, supportDto(item)) : json(response, 404, { detail: "Support session was not found." });
    }
    if (action === "end" && request.method === "POST") {
      if (!can("platform_support_session:write")) return deny();
      if (!item) return json(response, 404, { detail: "Support session was not found." });
      const input = await bodyFromRequest(request);
      const endReason = input.reason == null ? null : validReason(input.reason);
      if (input.reason != null && !endReason) return json(response, 422, { detail: "Invalid reason." });
      if (item.actor_user_id !== actorId && !can("platform_support_session:manage")) return deny();
      if (supportDto(item).state !== "active") return json(response, 410, { detail: "Support session is already closed." });
      Object.assign(item, { ended_at: new Date().toISOString(), ended_by: actorId, end_reason: endReason });
      recordPlatformEvent({ action: "platform_support.session_ended", actor_user_id: actorId, target_tenant_id: item.tenant_id, reason: endReason, support_session_id: sessionId });
      return json(response, 200, supportDto(item));
    }
    if ((action === "configuration" || action === "readiness") && request.method === "GET") {
      if (!can("platform_support_session:read")) return deny();
      if (!item) return json(response, 404, { detail: "Support session was not found." });
      if (item.actor_user_id !== actorId) return deny();
      if (supportDto(item).state !== "active") return json(response, 410, { detail: "Support session is closed." });
      if (!item.scopes.includes(action)) return deny();
      recordPlatformEvent({ action: "platform_support.data_viewed", actor_user_id: actorId, target_tenant_id: item.tenant_id, support_session_id: sessionId, scope: action });
      if (action === "configuration") {
        return json(response, 200, {
          session: supportDto(item),
          agents: (agents.get(item.tenant_id) ?? []).map(supportAgentDto),
          knowledge_bases: (knowledgeBases.get(item.tenant_id) ?? []).map((base) => ({
            knowledge_base_id: base.knowledge_base_id,
            name: base.name,
            status: base.status,
            source_count: base.source_count ?? 0,
            ready_source_count: base.ready_source_count ?? 0,
            updated_at: base.updated_at ?? null,
          })),
        });
      }
      const profile = onboarding.get(item.tenant_id);
      return json(response, 200, {
        session: supportDto(item),
        onboarding: profile ? { completed_steps: profile.completed_steps, use_case: profile.use_case, languages: profile.languages, timezone: profile.timezone } : null,
        entitlements: workspaceNames.has(item.tenant_id) ? entitlementsDto() : null,
        telephony: { trunk_configured: false, telephony_entitled: false, carrier_health: "not_measured" },
      });
    }
  }
  if (path === "/operations" && request.method === "GET") {
    if (!can("platform_operations:read")) return deny();
    const active = [...supportSessions.values()].filter((item) => supportDto(item).state === "active").length;
    const signal = (key, label, status, detail, metrics = {}) => ({ key, label, status, detail, metrics });
    return json(response, 200, {
      checked_at: new Date().toISOString(),
      environment: "test",
      signals: [
        signal("control_plane", "Control plane", "healthy", "The control plane is serving requests."),
        signal("database", "Database", "not_configured", "No PostgreSQL database is configured; in-memory repositories are in use."),
        signal("identity", "Identity verification", "healthy", "OIDC identity verification is configured."),
        signal("post_call_queue", "Post-call jobs", "healthy", "No post-call jobs are in the dead-letter state.", { queued: 0, running: 0, retry_wait: 0, succeeded: 0, dead_letter: 0 }),
        signal("live_providers", "Live provider traffic", "disabled", "Live provider traffic is disabled in this environment."),
        signal("provider_health", "Provider health", "not_measured", "No live provider health probe runs from the control plane."),
        signal("telephony", "Live telephony", "disabled", "Live telephony is disabled in this environment. Outbound runtime is not configured."),
        signal("carrier_health", "Carrier health", "not_measured", "No carrier health probe runs from the control plane."),
        signal("support_sessions", "Support sessions", "healthy", "Active read-only support sessions.", { active }),
      ],
    });
  }
  if (path === "/audit" && request.method === "GET") {
    if (!can("platform_audit:read")) return deny();
    return json(response, 200, platformAudit.slice(0, 50));
  }
  return json(response, 404, { detail: "Not found." });
}

async function handle(request, response) {
  const url = new URL(request.url ?? "/", issuer);
  if (url.pathname === "/health") return json(response, 200, { ok: true });
  if (url.pathname === "/reset" && request.method === "POST") {
    resetState();
    return json(response, 200, { ok: true });
  }
  // Test hook: close every active support session's window (mirrors database-clock expiry).
  if (url.pathname === "/expire-support-sessions" && request.method === "POST") {
    for (const item of supportSessions.values()) item.expires_at = new Date(Date.now() - 1000).toISOString();
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
  if (url.pathname === "/user_management/authorize" && request.method === "GET") {
    const redirectUri = url.searchParams.get("redirect_uri") ?? "";
    const state = url.searchParams.get("state") ?? "";
    const email = url.searchParams.get("email");
    if (!/^http:\/\/(127\.0\.0\.1|localhost):\d+\//.test(redirectUri)) return json(response, 400, { detail: "redirect_uri must be local." });
    if (email && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      const code = randomBytes(16).toString("hex");
      authCodes.set(code, identityFor(email));
      const target = new URL(redirectUri);
      target.searchParams.set("code", code);
      if (state) target.searchParams.set("state", state);
      response.writeHead(302, { location: target.toString() });
      return response.end();
    }
    const signUp = url.searchParams.get("screen_hint") === "sign-up";
    response.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" });
    return response.end(`<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Offline identity provider</title></head>
<body style="font-family:system-ui;max-width:28rem;margin:4rem auto">
<p><strong>Offline identity provider — test double.</strong> Stands in for WorkOS hosted sign-in on this machine only.</p>
<h1>${signUp ? "Create your account" : "Sign in"}</h1>
<form method="get" action="/user_management/authorize">
<input type="hidden" name="redirect_uri" value="${escapeHtml(redirectUri)}"><input type="hidden" name="state" value="${escapeHtml(state)}">
<label>Email <input type="email" name="email" required autocomplete="email"></label>
<button type="submit">${signUp ? "Create account" : "Continue"}</button></form></body></html>`);
  }
  if (url.pathname === "/user_management/authenticate" && request.method === "POST") {
    const body = await bodyFromRequest(request);
    let identity = null;
    if (body.grant_type === "authorization_code") {
      identity = authCodes.get(body.code) ?? null;
      authCodes.delete(body.code);
    } else if (body.grant_type === "refresh_token") {
      identity = refreshTokens.get(body.refresh_token) ?? null;
    }
    if (!identity) return json(response, 400, { error: "invalid_grant", error_description: "Unknown or used code." });
    const refreshToken = randomBytes(24).toString("hex");
    refreshTokens.set(refreshToken, identity);
    return json(response, 200, {
      user: workosUser(identity),
      access_token: token(identity.id, false, identity.email),
      refresh_token: refreshToken,
      authentication_method: "Password",
    });
  }
  if (url.pathname.toLowerCase().includes("jwks")) {
    return json(response, 200, { keys: [{ ...publicJwk, kid: signingKeyId, alg: "RS256", use: "sig" }] });
  }
  if (url.pathname === "/user_management/sessions/logout") {
    const returnTo = url.searchParams.get("return_to") || "/sign-in";
    response.writeHead(302, { location: new URL(returnTo, `http://127.0.0.1:${appPort}`).toString() });
    return response.end();
  }
  if (url.pathname === "/v1/me") {
    const subject = subjectFromRequest(request);
    if (!subject) return json(response, 401, { detail: "Authentication required." });
    const userId = userIdForSubject(subject);
    const memberships = subject === "user-none" ? [] : [workspaceA, workspaceB].flatMap((tenantId) => {
      const role = members.get(tenantId).get(userId);
      return role ? [{ ...membershipDto(tenantId, userId, role), capabilities: roleCapabilities[role] }] : [];
    });
    const platformRole = platformStaff.get(userId)?.role ?? null;
    return json(response, 200, {
      user_id: userId,
      email: `${subject}@example.test`,
      is_active: true,
      is_platform_admin: platformRole === "platform_admin",
      platform_role: platformRole,
      platform_capabilities: platformRole ? platformCapabilities[platformRole] : [],
      memberships: PLATFORM_SUBJECTS.has(subject) ? [] : memberships,
    });
  }
  if (url.pathname === "/v1/invitations/accept" && request.method === "POST") {
    const subject = subjectFromRequest(request);
    if (!subject) return json(response, 401, { detail: "Authentication required." });
    const input = await bodyFromRequest(request);
    const invitation = invitations.get(String(input.token ?? ""));
    if (!invitation) return json(response, 404, { detail: "Invitation was not found." });
    if (invitation.accepted_at) return json(response, 409, { detail: "Invitation was already accepted." });
    if (Date.parse(invitation.expires_at) <= Date.now()) return json(response, 410, { detail: "Invitation has expired." });
    if (invitation.email !== `${subject}@example.test`) {
      return json(response, 403, { detail: "Authenticated identity does not match invitation email." });
    }
    const userId = userIdForSubject(subject);
    members.get(invitation.tenant_id).set(userId, invitation.role);
    invitation.accepted_at = new Date().toISOString();
    invitation.accepted_by = userId;
    // FastAPI returns the WorkspaceMembership model here, without capabilities.
    return json(response, 200, membershipDto(invitation.tenant_id, userId, invitation.role));
  }
  if (url.pathname.startsWith("/v1/platform/")) return handlePlatform(request, response, url);
  const tenant = tenantFromRequest(request);
  if (!subjectFromRequest(request)) return json(response, 401, { detail: "Authentication required." });
  if (!tenant || !agents.has(tenant)) return json(response, 403, { detail: "Workspace required." });

  // ── Members and invitations (mirrors control_plane/routes/identity.py) ────
  const organizationMatch = url.pathname.match(/^\/v1\/organizations\/([^/]+)\/(members|invitations)(?:\/([^/]+))?$/i);
  if (organizationMatch) {
    const [, pathTenant, collection, memberId] = organizationMatch;
    if (pathTenant !== tenant) return json(response, 403, { detail: "Tenant access denied." });
    const actorId = userIdForSubject(subjectFromRequest(request));
    const actorRole = members.get(tenant).get(actorId);
    const required = request.method === "GET" ? "member:read" : "member:write";
    if (!actorRole || !roleCapabilities[actorRole].includes(required)) {
      return json(response, 403, { detail: "Permission denied." });
    }
    const tenantMembers = members.get(tenant);
    if (collection === "members" && !memberId && request.method === "GET") {
      const listed = [...tenantMembers.entries()]
        .map(([userId, role]) => membershipDto(tenant, userId, role))
        .sort((left, right) => left.role.localeCompare(right.role) || left.user_id.localeCompare(right.user_id));
      return json(response, 200, listed);
    }
    if (collection === "invitations" && !memberId && request.method === "POST") {
      if (actorRole !== "tenant_admin") return json(response, 403, { detail: "Only tenant administrators may invite members." });
      const input = await bodyFromRequest(request);
      const role = input.role ?? "tenant_viewer";
      const email = String(input.email ?? "").trim().toLowerCase();
      if (!launchRoles.has(role) || email.length < 3) return json(response, 422, { detail: "Invalid invitation." });
      const invitationToken = `offline_invitation_${String(nextInvitation).padStart(4, "0")}_${randomBytes(12).toString("base64url")}`;
      const invitation = {
        invitation_id: fixtureId("f", nextInvitation++),
        tenant_id: tenant,
        email,
        role,
        invited_by: actorId,
        expires_at: new Date(Date.now() + 72 * 3_600_000).toISOString(),
        accepted_at: null,
        accepted_by: null,
        created_at: new Date().toISOString(),
      };
      invitations.set(invitationToken, invitation);
      return json(response, 201, { ...invitation, token: invitationToken });
    }
    if (collection === "members" && memberId && (request.method === "PATCH" || request.method === "DELETE")) {
      const currentRole = tenantMembers.get(memberId);
      if (!currentRole) return json(response, 404, { detail: "Membership was not found." });
      const nextRole = request.method === "PATCH" ? (await bodyFromRequest(request)).role : null;
      if (request.method === "PATCH" && !launchRoles.has(nextRole)) return json(response, 422, { detail: "Invalid role." });
      const adminCount = [...tenantMembers.values()].filter((role) => role === "tenant_admin").length;
      if (currentRole === "tenant_admin" && nextRole !== "tenant_admin" && adminCount === 1) {
        return json(response, 409, { detail: "A workspace must retain one tenant administrator." });
      }
      if (request.method === "DELETE") {
        tenantMembers.delete(memberId);
        response.writeHead(204); return response.end();
      }
      tenantMembers.set(memberId, nextRole);
      return json(response, 200, membershipDto(tenant, memberId, nextRole));
    }
  }

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
    return json(response, 200, entitlementsDto());
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
  if (url.pathname === "/v1/webhook-targets" && request.method === "GET") {
    return json(response, 200, webhookTargets.get(tenant) ?? []);
  }
  if (url.pathname === "/v1/webhook-targets" && request.method === "POST") {
    const input = await bodyFromRequest(request);
    if (!String(input.url ?? "").startsWith("https://")) return json(response, 422, { detail: "Webhook endpoint must use HTTPS." });
    const now = new Date().toISOString();
    const target = {
      target_id: fixtureId("8", (webhookTargets.get(tenant) ?? []).length + 1),
      name: String(input.name), url: String(input.url), state: "active", created_at: now, updated_at: now,
      signature_header: "X-Wavia-Signature",
    };
    webhookTargets.set(tenant, [...(webhookTargets.get(tenant) ?? []), target]);
    return json(response, 201, { ...target, signing_secret: "whsec_offline_fixture_secret_value" });
  }
  const disableMatch = url.pathname.match(/^\/v1\/webhook-targets\/([^/]+)\/disable$/);
  if (disableMatch && request.method === "POST") {
    const target = (webhookTargets.get(tenant) ?? []).find((item) => item.target_id === disableMatch[1]);
    if (!target) return json(response, 404, { detail: "Webhook target not found." });
    Object.assign(target, { state: "disabled", updated_at: new Date().toISOString() });
    return json(response, 200, target);
  }
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
}).listen(port, process.env.WAVIA_E2E_FIXTURE_BIND ?? host);

function shutdown() {
  server.closeAllConnections?.();
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 500).unref();
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
