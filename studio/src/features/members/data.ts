import "server-only";

import { controlPlaneRequest } from "@/data/control-plane";
import type { StudioServerSession } from "@/data/dto";
import { workspaceMemberListSchema } from "@/data/schema";

/** Tenant-scoped member list; FastAPI repeats member:read and tenant access checks. */
export function loadWorkspaceMembers(session: StudioServerSession, tenantId: string) {
  return controlPlaneRequest(`/v1/organizations/${tenantId}/members`, {
    schema: workspaceMemberListSchema,
    session,
    selectedTenantId: tenantId,
  });
}
