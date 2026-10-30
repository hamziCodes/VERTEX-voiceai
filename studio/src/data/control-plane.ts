import "server-only";

import { randomUUID } from "node:crypto";

import type { z } from "zod";

import type { StudioServerSession } from "./dto";
import { parseControlPlaneDto } from "./schema";

const DEFAULT_TIMEOUT_MS = 8_000;
const ALLOWED_CALLER_HEADERS = new Set([
  "accept",
  "content-type",
  "idempotency-key",
  "if-match",
]);

type SafeErrorCode =
  | "configuration_error"
  | "conflict"
  | "forbidden"
  | "invalid_request"
  | "invalid_upstream_response"
  | "rate_limited"
  | "session_expired"
  | "session_required"
  | "upstream_timeout"
  | "upstream_unavailable"
  | "workspace_required";

interface ErrorDescriptor {
  code: SafeErrorCode;
  message: string;
}

const UPSTREAM_ERRORS: Readonly<Record<number, ErrorDescriptor>> = {
  401: { code: "session_expired", message: "Your session has expired." },
  403: { code: "forbidden", message: "You do not have permission for this action." },
  409: { code: "conflict", message: "This record changed. Refresh and try again." },
  422: { code: "invalid_request", message: "The request could not be accepted." },
  429: { code: "rate_limited", message: "Too many requests. Try again shortly." },
  503: { code: "upstream_unavailable", message: "The service is temporarily unavailable." },
};

export class ControlPlaneError extends Error {
  readonly code: SafeErrorCode;
  readonly status: number;
  readonly requestId?: string;
  readonly retryAfter?: string;

  constructor(
    descriptor: ErrorDescriptor,
    status: number,
    options: { requestId?: string; retryAfter?: string } = {},
  ) {
    super(descriptor.message);
    this.name = "ControlPlaneError";
    this.code = descriptor.code;
    this.status = status;
    this.requestId = options.requestId;
    this.retryAfter = options.retryAfter;
  }
}

export interface ControlPlaneRequestOptions<T> {
  schema: z.ZodType<T>;
  session: StudioServerSession | null;
  selectedTenantId: string | null;
  method?: "DELETE" | "GET" | "PATCH" | "POST" | "PUT";
  headers?: HeadersInit;
  json?: unknown;
  requestId?: string;
  timeoutMs?: number;
}

function safeHeaders(options: ControlPlaneRequestOptions<unknown>): Headers {
  const headers = new Headers();
  const callerHeaders = new Headers(options.headers);

  for (const [name, value] of callerHeaders.entries()) {
    if (ALLOWED_CALLER_HEADERS.has(name.toLowerCase())) {
      headers.set(name, value);
    }
  }

  headers.set("authorization", `Bearer ${options.session?.accessToken ?? ""}`);
  headers.set("x-tenant-id", options.selectedTenantId ?? "");
  headers.set("x-request-id", options.requestId ?? randomUUID());
  if (options.json !== undefined) {
    headers.set("content-type", "application/json");
  }
  return headers;
}

function requireRequestContext<T>(options: ControlPlaneRequestOptions<T>): void {
  if (!options.session?.accessToken) {
    throw new ControlPlaneError(
      { code: "session_required", message: "Sign in to continue." },
      401,
    );
  }
  if (!options.selectedTenantId) {
    throw new ControlPlaneError(
      { code: "workspace_required", message: "Select a workspace to continue." },
      400,
    );
  }
}

function controlPlaneUrl(path: string): URL {
  const baseUrl = process.env.WAVIA_CONTROL_PLANE_URL;
  if (!baseUrl) {
    throw new ControlPlaneError(
      { code: "configuration_error", message: "Studio is not configured." },
      500,
    );
  }
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw new ControlPlaneError(
      { code: "invalid_request", message: "The control-plane path is invalid." },
      400,
    );
  }

  let base: URL;
  try {
    base = new URL(baseUrl);
  } catch {
    throw new ControlPlaneError(
      { code: "configuration_error", message: "Studio is not configured." },
      500,
    );
  }
  const url = new URL(path, base);
  if (url.origin !== base.origin) {
    throw new ControlPlaneError(
      { code: "invalid_request", message: "The control-plane path is invalid." },
      400,
    );
  }
  return url;
}

function upstreamError(response: Response, requestId: string): ControlPlaneError {
  const descriptor = UPSTREAM_ERRORS[response.status] ?? {
    code: "upstream_unavailable",
    message: "The service could not complete the request.",
  };
  return new ControlPlaneError(descriptor, response.status, {
    requestId: response.headers.get("x-request-id") ?? requestId,
    retryAfter: response.headers.get("retry-after") ?? undefined,
  });
}

export async function controlPlaneRequest<T>(
  path: string,
  options: ControlPlaneRequestOptions<T>,
): Promise<T> {
  requireRequestContext(options);

  const headers = safeHeaders(options);
  const requestId = headers.get("x-request-id") ?? randomUUID();
  const url = controlPlaneUrl(path);
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  );

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers,
      body: options.json === undefined ? undefined : JSON.stringify(options.json),
      cache: "no-store",
      signal: controller.signal,
    });
  } catch {
    if (controller.signal.aborted) {
      throw new ControlPlaneError(
        { code: "upstream_timeout", message: "The service took too long to respond." },
        504,
        { requestId },
      );
    }
    throw new ControlPlaneError(
      { code: "upstream_unavailable", message: "The service is temporarily unavailable." },
      503,
      { requestId },
    );
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    throw upstreamError(response, requestId);
  }

  let payload: unknown;
  try {
    payload = await response.json();
    return parseControlPlaneDto(options.schema, payload);
  } catch (error) {
    if (error instanceof ControlPlaneError) {
      throw error;
    }
    throw new ControlPlaneError(
      {
        code: "invalid_upstream_response",
        message: "The service returned an invalid response.",
      },
      502,
      {
        requestId: response.headers.get("x-request-id") ?? requestId,
      },
    );
  }
}
