import "server-only";

import type { StudioServerSession } from "@/data/dto";
import { controlPlaneRequest } from "@/data/control-plane";
import { onboardingResponseSchema } from "@/data/schema";

export function loadOnboarding(session: StudioServerSession, tenantId: string) {
  return controlPlaneRequest("/v1/onboarding", {
    schema: onboardingResponseSchema,
    session,
    selectedTenantId: tenantId,
  });
}
