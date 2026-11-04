import "server-only";

import { controlPlaneRequest } from "@/data/control-plane";
import { apiKeyListSchema, type APIKeyDto } from "@/data/schema";
import { requireWorkspace } from "@/auth/workspace";

export async function listAPIKeys(): Promise<APIKeyDto[]> {
  const { session, membership } = await requireWorkspace("api_key:read");
  const res = await controlPlaneRequest("/v1/api-keys", {
    schema: apiKeyListSchema,
    session,
    selectedTenantId: membership.tenant_id,
  });
  return res.keys;
}
