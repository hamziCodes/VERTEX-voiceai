import "server-only";

import { controlPlaneRequest } from "@/data/control-plane";
import type { StudioServerSession } from "@/data/dto";
import {
  operationsSnapshotSchema,
  platformAuditListSchema,
  platformStaffListSchema,
  supportConfigurationSchema,
  supportReadinessSchema,
  supportSessionListSchema,
  supportSessionSchema,
  tenantDirectoryPageSchema,
  tenantSummarySchema,
} from "@/data/schema";

export const DIRECTORY_PAGE_SIZE = 25;
export const DIRECTORY_MAX_OFFSET = 10_000;
export const AUDIT_PAGE_SIZE = 50;

const platform = { selectedTenantId: null, scope: "platform" } as const;

/** Bounded tenant directory; FastAPI repeats `platform_tenant:read`. */
export function loadTenantDirectory(session: StudioServerSession, query: { q?: string; offset: number }) {
  const params = new URLSearchParams({ limit: String(DIRECTORY_PAGE_SIZE), offset: String(query.offset) });
  if (query.q) params.set("q", query.q);
  return controlPlaneRequest(`/v1/platform/tenants?${params.toString()}`, {
    schema: tenantDirectoryPageSchema,
    session,
    ...platform,
  });
}

/** Safe tenant summary. FastAPI writes a `platform_tenant.viewed` audit event for every read. */
export function loadTenantSummary(session: StudioServerSession, tenantId: string) {
  return controlPlaneRequest(`/v1/platform/tenants/${encodeURIComponent(tenantId)}`, {
    schema: tenantSummarySchema,
    session,
    ...platform,
  });
}

export function loadPlatformStaff(session: StudioServerSession) {
  return controlPlaneRequest("/v1/platform/staff", { schema: platformStaffListSchema, session, ...platform });
}

export function loadPlatformAudit(session: StudioServerSession) {
  return controlPlaneRequest(`/v1/platform/audit?limit=${AUDIT_PAGE_SIZE}`, {
    schema: platformAuditListSchema,
    session,
    ...platform,
  });
}

export const SUPPORT_LIST_SIZE = 50;

export function loadSupportSessions(session: StudioServerSession, state: "active" | "recent") {
  return controlPlaneRequest(`/v1/platform/support-sessions?state=${state}&limit=${SUPPORT_LIST_SIZE}`, {
    schema: supportSessionListSchema,
    session,
    ...platform,
  });
}

export function loadSupportSession(session: StudioServerSession, sessionId: string) {
  return controlPlaneRequest(`/v1/platform/support-sessions/${encodeURIComponent(sessionId)}`, {
    schema: supportSessionSchema,
    session,
    ...platform,
  });
}

/** Every call is a support read: FastAPI checks owner, expiry and scope and writes an audit event. */
export function loadSupportConfiguration(session: StudioServerSession, sessionId: string) {
  return controlPlaneRequest(`/v1/platform/support-sessions/${encodeURIComponent(sessionId)}/configuration`, {
    schema: supportConfigurationSchema,
    session,
    ...platform,
  });
}

export function loadSupportReadiness(session: StudioServerSession, sessionId: string) {
  return controlPlaneRequest(`/v1/platform/support-sessions/${encodeURIComponent(sessionId)}/readiness`, {
    schema: supportReadinessSchema,
    session,
    ...platform,
  });
}

export function loadOperationsSnapshot(session: StudioServerSession) {
  return controlPlaneRequest("/v1/platform/operations", { schema: operationsSnapshotSchema, session, ...platform });
}
