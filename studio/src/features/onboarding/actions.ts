"use server";

import { revalidatePath } from "next/cache";

import { requireWorkspace } from "@/auth/workspace";
import { ControlPlaneError, controlPlaneRequest } from "@/data/control-plane";
import { onboardingResponseSchema } from "@/data/schema";

import type { OnboardingValues } from "./onboarding-form";

export async function saveOnboardingAction(values: OnboardingValues): Promise<{ state: "saved" | "error"; message?: string }> {
  const { session, membership } = await requireWorkspace("onboarding:write");
  try {
    await controlPlaneRequest("/v1/onboarding", {
      method: "PATCH",
      json: values,
      schema: onboardingResponseSchema,
      session,
      selectedTenantId: membership.tenant_id,
    });
    revalidatePath("/onboarding");
    return { state: "saved" };
  } catch (error) {
    return { state: "error", message: error instanceof ControlPlaneError ? error.message : "Onboarding could not be saved." };
  }
}
