import "server-only";

import type { StudioServerSession } from "@/data/dto";
import { controlPlaneRequest } from "@/data/control-plane";
import { usageSchema } from "@/data/schema";

export function getUsage(session: StudioServerSession, tenantId: string) {
  return controlPlaneRequest("/v1/usage", {
    schema: usageSchema,
    session,
    selectedTenantId: tenantId,
  });
}
