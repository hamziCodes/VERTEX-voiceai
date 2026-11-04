"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { controlPlaneRequest } from "@/data/control-plane";
import { createApiKeyResponseSchema, type CreateApiKeyResponseDto } from "@/data/schema";
import { requireWorkspace } from "@/auth/workspace";
import type { CreateAPIKeyInput } from "./types";

export async function createAPIKeyAction(
  input: CreateAPIKeyInput
): Promise<{ success: boolean; data?: CreateApiKeyResponseDto; error?: string }> {
  try {
    const { session, membership } = await requireWorkspace("api_key:write");
    const res = await controlPlaneRequest("/v1/api-keys", {
      method: "POST",
      schema: createApiKeyResponseSchema,
      session,
      selectedTenantId: membership.tenant_id,
      json: {
        name: input.name,
        role: input.role,
        scopes: input.scopes,
        expires_at: input.expires_at || null,
      },
    });
    revalidatePath("/developers/api-keys");
    return { success: true, data: res };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to create API key." };
  }
}
export async function revokeAPIKeyAction(
  keyId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const { session, membership } = await requireWorkspace("api_key:write");
    await controlPlaneRequest(`/v1/api-keys/${keyId}`, {
      method: "DELETE",
      schema: z.null(),
      session,
      selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/developers/api-keys");
    return { success: true };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to revoke API key." };
  }
}
