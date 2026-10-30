import { createSign, generateKeyPairSync } from "node:crypto";
import { createServer } from "node:http";

const host = "127.0.0.1";
const port = 3211;
const issuer = `http://${host}:${port}/`;
const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const publicJwk = publicKey.export({ format: "jwk" });
const workspaceA = "11111111-1111-4111-8111-111111111111";
const workspaceB = "22222222-2222-4222-8222-222222222222";
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

function resetState() {
  onboarding = new Map([[workspaceA, structuredClone(initialOnboarding)], [workspaceB, structuredClone(initialOnboarding)]]);
  const viewerAgent = { ...structuredClone(templateConfig), name: "Viewer-safe assistant", agent_id: "44444444-4444-4444-8444-444444444444", draft_revision: 1, version: 1, published_at: null, is_published: false };
  agents = new Map([[workspaceA, []], [workspaceB, [viewerAgent]]]);
  versions = new Map();
  nextAgent = 1;
}

resetState();

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

async function bodyFromRequest(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString("utf8")) : {};
}

function agentId() {
  const suffix = String(nextAgent++).padStart(12, "0");
  return `33333333-3333-4333-8333-${suffix}`;
}

function findAgent(tenant, id) {
  return (agents.get(tenant) ?? []).find((agent) => agent.agent_id === id);
}

async function handle(request, response) {
  const url = new URL(request.url ?? "/", issuer);
  if (url.pathname === "/health") return json(response, 200, { ok: true });
  if (url.pathname === "/reset" && request.method === "POST") {
    resetState();
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
    const memberships = subject === "user-none" ? [] : [
      { user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", tenant_id: workspaceA, tenant_name: "Alpha workspace", role: "tenant_admin", created_at: createdAt },
      { user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", tenant_id: workspaceB, tenant_name: "Beta workspace", role: "tenant_viewer", created_at: createdAt },
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
