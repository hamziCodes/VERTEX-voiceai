"use server";

import { revalidatePath } from "next/cache";

import { controlPlaneRequest } from "@/data/control-plane";
import { telephonyPolicySchema, telephonySettingsSchema, type TelephonyPolicyDto } from "@/data/schema";
import { requireWorkspace } from "@/auth/workspace";

export async function saveTelephonyPolicyAction(policy: TelephonyPolicyDto): Promise<{ success: boolean; error?: string }> {
  try {
    const { session, membership } = await requireWorkspace("telephony:write");
    const validated = telephonyPolicySchema.parse(policy);
    await controlPlaneRequest("/v1/telephony/settings", {
      method: "PUT",
      schema: telephonySettingsSchema,
      session,
      selectedTenantId: membership.tenant_id,
      json: validated,
    });
    revalidatePath("/channels/telephony");
    return { success: true };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to update telephony policy." };
  }
}
