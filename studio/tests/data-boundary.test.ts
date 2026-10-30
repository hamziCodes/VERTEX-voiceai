import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

import {
  ControlPlaneError,
  controlPlaneRequest,
} from "@/data/control-plane";

const responseSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
});

const serverSession = { accessToken: "test-server-token" };
const tenantId = "00000000-0000-4000-8000-000000000001";
const validPayload = {
  id: "10000000-0000-4000-8000-000000000001",
  name: "Wavia test workspace",
};

function requestOptions(
  overrides: Partial<Parameters<typeof controlPlaneRequest>[1]> = {},
) {
  return {
    schema: responseSchema,
    session: serverSession,
    selectedTenantId: tenantId,
    ...overrides,
  };
}

describe("controlPlaneRequest", () => {
  beforeEach(() => {
    process.env.WAVIA_CONTROL_PLANE_URL = "https://control-plane.test";
  });

  afterEach(() => {
    delete process.env.WAVIA_CONTROL_PLANE_URL;
    vi.useRealTimers();
  });

  it("refuses a request without a server session before any network call", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    await expect(
      controlPlaneRequest("/v1/me", requestOptions({ session: null })),
    ).rejects.toMatchObject({
      code: "session_required",
      status: 401,
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("refuses a request without a selected workspace before any network call", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    await expect(
      controlPlaneRequest(
        "/v1/agents",
        requestOptions({ selectedTenantId: null }),
      ),
    ).rejects.toMatchObject({
      code: "workspace_required",
      status: 400,
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("allows an explicit identity-scoped bootstrap request without a workspace", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json(validPayload));

    await expect(
      controlPlaneRequest(
        "/v1/me",
        requestOptions({ selectedTenantId: null, scope: "identity" }),
      ),
    ).resolves.toEqual(validPayload);

    const [, init] = fetchSpy.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get("authorization")).toBe("Bearer test-server-token");
    expect(headers.has("x-tenant-id")).toBe(false);
  });

  it.each(["https://attacker.test/v1/me", "//attacker.test/v1/me", "v1/me"])(
    "refuses non-local control-plane path %s before credentials can leave",
    async (path) => {
      const fetchSpy = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValue(Response.json(validPayload));

      await expect(
        controlPlaneRequest(path, requestOptions()),
      ).rejects.toMatchObject({
        code: "invalid_request",
        status: 400,
      });
      expect(fetchSpy).not.toHaveBeenCalled();
    },
  );

  it("times out a stalled upstream request", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockImplementation((_, init) =>
      new Promise((_, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        });
      }),
    );

    const pending = controlPlaneRequest(
      "/v1/me",
      requestOptions({ timeoutMs: 25 }),
    );
    const rejection = expect(pending).rejects.toMatchObject({
      code: "upstream_timeout",
      status: 504,
    });
    await vi.advanceTimersByTimeAsync(25);

    await rejection;
  });

  it("rejects a successful response that violates its DTO schema", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ id: "not-a-uuid", name: "" }),
    );

    await expect(
      controlPlaneRequest("/v1/me", requestOptions()),
    ).rejects.toMatchObject({
      code: "invalid_upstream_response",
      status: 502,
    });
  });

  it.each([
    [401, "session_expired"],
    [403, "forbidden"],
    [409, "conflict"],
    [422, "invalid_request"],
    [429, "rate_limited"],
    [503, "upstream_unavailable"],
  ])("maps upstream status %i to safe code %s", async (status, code) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json(
        { detail: "raw upstream detail must not escape" },
        {
          status,
          headers: { "x-request-id": "upstream-request-id" },
        },
      ),
    );

    await expect(
      controlPlaneRequest("/v1/me", requestOptions()),
    ).rejects.toMatchObject({
      code,
      status,
      requestId: "upstream-request-id",
    });
  });

  it("preserves the request ID and only forwards explicitly allowed headers", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json(validPayload));

    await expect(
      controlPlaneRequest(
        "/v1/me",
        requestOptions({
          requestId: "caller-request-id",
          headers: {
            Accept: "application/json",
            Authorization: "Bearer attacker-controlled",
            Cookie: "session=attacker-controlled",
            "Idempotency-Key": "safe-idempotency-key",
            "X-Tenant-Id": "attacker-controlled-tenant",
          },
        }),
      ),
    ).resolves.toEqual(validPayload);

    const [, init] = fetchSpy.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get("authorization")).toBe("Bearer test-server-token");
    expect(headers.get("x-tenant-id")).toBe(tenantId);
    expect(headers.get("x-request-id")).toBe("caller-request-id");
    expect(headers.get("idempotency-key")).toBe("safe-idempotency-key");
    expect(headers.get("accept")).toBe("application/json");
    expect(headers.has("cookie")).toBe(false);
  });

  it("forwards multipart bodies without overriding the generated boundary", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json(validPayload));
    const form = new FormData();
    form.set("source", new File(["refund policy"], "refunds.txt", { type: "text/plain" }));

    await expect(controlPlaneRequest("/v1/knowledge-bases/example/sources", requestOptions({ method: "POST", body: form }))).resolves.toEqual(validPayload);

    const [, init] = fetchSpy.mock.calls[0];
    expect(init?.body).toBe(form);
    expect(new Headers(init?.headers).has("content-type")).toBe(false);
  });

  it("rejects ambiguous JSON and raw-body requests before any network call", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    await expect(controlPlaneRequest("/v1/knowledge-bases", requestOptions({ method: "POST", json: { name: "Policies" }, body: new FormData() }))).rejects.toMatchObject({
      code: "invalid_request",
      status: 400,
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("parses a successful empty response through an explicit null schema", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));

    await expect(controlPlaneRequest("/v1/knowledge-bases/example/sources/example", requestOptions({ method: "DELETE", schema: z.null() }))).resolves.toBeNull();
  });

  it("never exposes tokens or raw upstream bodies in errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json(
        {
          access_token: serverSession.accessToken,
          password: "test-password-value",
        },
        { status: 503 },
      ),
    );

    let caught: unknown;
    try {
      await controlPlaneRequest("/v1/me", requestOptions());
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(ControlPlaneError);
    const serialized = JSON.stringify(caught);
    expect(serialized).not.toContain(serverSession.accessToken);
    expect(serialized).not.toContain("test-password-value");
    expect(String(caught)).not.toContain(serverSession.accessToken);
    expect(String(caught)).not.toContain("test-password-value");
  });
});
