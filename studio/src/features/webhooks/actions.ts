"use server";

import { revalidatePath } from "next/cache";

import { requireWorkspace } from "@/auth/workspace";
import { ControlPlaneError, controlPlaneRequest } from "@/data/control-plane";
import {
  createdWebhookTargetSchema,
  reviewDecisionResponseSchema,
  webhookTargetSchema,
  type CreatedWebhookTargetDto,
} from "@/data/schema";

export type CreateWebhookResult =
  | { state: "created"; target: CreatedWebhookTargetDto }
  | { state: "error"; message: string };

export async function createWebhookTargetAction(input: { name: string; url: string }): Promise<CreateWebhookResult> {
  const name = input.name.trim();
  const url = input.url.trim();
  if (!name || name.length > 128) return { state: "error", message: "Enter a name of up to 128 characters." };
  if (!url.startsWith("https://")) return { state: "error", message: "The endpoint must use HTTPS." };
  try {
    const { session, membership } = await requireWorkspace("webhook:write");
    const target = await controlPlaneRequest("/v1/webhook-targets", {
      method: "POST",
      json: { name, url },
      schema: createdWebhookTargetSchema,
      session,
      selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/developers/webhooks");
    return { state: "created", target };
  } catch (error) {
    if (error instanceof ControlPlaneError && error.status === 422) {
      return {
        state: "error",
        message: "That endpoint was refused: it must be HTTPS on port 443 and resolve only to public addresses.",
      };
    }
    return { state: "error", message: "The endpoint could not be created. Try again." };
  }
}

export async function disableWebhookTargetAction(targetId: string): Promise<{ ok: boolean }> {
  try {
    const { session, membership } = await requireWorkspace("webhook:write");
    await controlPlaneRequest(`/v1/webhook-targets/${encodeURIComponent(targetId)}/disable`, {
      method: "POST",
      schema: webhookTargetSchema,
      session,
      selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/developers/webhooks");
    return { ok: true };
  } catch {
    return { ok: false };
  }
}

/** Approve or reject a flagged post-call result; approval releases its webhooks. */
export async function decideReviewAction(formData: FormData): Promise<void> {
  const callId = String(formData.get("callId") ?? "");
  const decision = formData.get("decision") === "reject" ? "reject" : "approve";
  const note = String(formData.get("note") ?? "").slice(0, 1000);
  const { session, membership } = await requireWorkspace("extraction:write");
  await controlPlaneRequest(`/v1/conversations/${encodeURIComponent(callId)}/review`, {
    method: "POST",
    json: { decision, note },
    schema: reviewDecisionResponseSchema,
    session,
    selectedTenantId: membership.tenant_id,
  });
  revalidatePath(`/conversations/${callId}`);
}
