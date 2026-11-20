import "server-only";

import { controlPlaneRequest } from "@/data/control-plane";
import { telephonySettingsSchema, type TelephonySettingsDto } from "@/data/schema";
import { requireWorkspace } from "@/auth/workspace";

export async function getTelephonySettings(): Promise<TelephonySettingsDto> {
  const { session, membership } = await requireWorkspace("telephony:read");
  return controlPlaneRequest("/v1/telephony/settings", {
    schema: telephonySettingsSchema,
    session,
    selectedTenantId: membership.tenant_id,
  });
}
