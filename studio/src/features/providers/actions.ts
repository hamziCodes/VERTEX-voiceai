"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { controlPlaneRequest } from "@/data/control-plane";
import { providerCredentialSchema, type ProviderCredentialDto } from "@/data/schema";
import { requireWorkspace } from "@/auth/workspace";
import type { StoreCredentialInput } from "./types";

export async function storeProviderCredentialAction(
  input: StoreCredentialInput
): Promise<{ success: boolean; data?: ProviderCredentialDto; error?: string }> {
  try {
    const { session, membership } = await requireWorkspace("provider_credential:write");
    const res = await controlPlaneRequest("/v1/provider-credentials", {
      method: "POST",
      schema: providerCredentialSchema,
      session,
      selectedTenantId: membership.tenant_id,
      json: {
        provider_id: input.provider_id,
        secret: input.secret,
        credential_type: input.credential_type || "api_key",
        reference: input.reference || "default",
      },
    });
    revalidatePath("/settings/providers");
    return { success: true, data: res };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to store provider credential." };
  }
}
export async function revokeProviderCredentialAction(
  credentialId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const { session, membership } = await requireWorkspace("provider_credential:write");
    await controlPlaneRequest(`/v1/provider-credentials/${credentialId}`, {
      method: "DELETE",
      schema: z.null(),
      session,
      selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/settings/providers");
    return { success: true };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to revoke provider credential." };
  }
}
