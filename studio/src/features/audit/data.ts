import "server-only";

import type { StudioServerSession } from "@/data/dto";
import { controlPlaneRequest } from "@/data/control-plane";
import { auditResponseSchema } from "@/data/schema";

export async function getAuditEvents(session: StudioServerSession, tenantId: string) {
  const response = await controlPlaneRequest("/v1/audit", {
    schema: auditResponseSchema,
    session,
    selectedTenantId: tenantId,
  });
  return response.events;
}
