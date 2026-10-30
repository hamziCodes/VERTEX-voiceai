import { createSign, generateKeyPairSync } from "node:crypto";
import { createServer } from "node:http";

const host = "127.0.0.1";
const port = 3211;
const issuer = `http://${host}:${port}/`;
const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const publicJwk = publicKey.export({ format: "jwk" });
const workspaceA = "11111111-1111-4111-8111-111111111111";
const workspaceB = "22222222-2222-4222-8222-222222222222";

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

const server = createServer((request, response) => {
  const url = new URL(request.url ?? "/", issuer);
  if (url.pathname === "/health") return json(response, 200, { ok: true });
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
  return json(response, 404, { detail: "Offline fixture route not found." });
}).listen(port, host);

function shutdown() {
  server.closeAllConnections?.();
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 500).unref();
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
