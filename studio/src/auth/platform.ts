import "server-only";

import { notFound, redirect } from "next/navigation";

import { ControlPlaneError, controlPlaneRequest } from "@/data/control-plane";
import { platformIdentitySchema, type PlatformIdentityDto } from "@/data/schema";

import { hasPlatformCapability, type PlatformCapability } from "./platform-permissions";
import { requireSession, type StudioSession } from "./session";

export { hasPlatformCapability, type PlatformCapability } from "./platform-permissions";

export interface PlatformContext {
  session: StudioSession;
  identity: PlatformIdentityDto;
}

/**
 * Gate for the internal `/admin` area. FastAPI decides staff membership from the durable
 * platform role; customers get a plain not-found so the area's existence is not advertised.
 * Staff missing a capability are sent to the overview without any data being loaded.
 */
export async function requirePlatform(capability?: PlatformCapability): Promise<PlatformContext> {
  const session = await requireSession();
  let identity: PlatformIdentityDto;
  try {
    identity = await controlPlaneRequest("/v1/platform/me", {
      schema: platformIdentitySchema,
      session,
      selectedTenantId: null,
      scope: "platform",
    });
  } catch (error) {
    if (error instanceof ControlPlaneError && error.status === 403) notFound();
    throw error;
  }
  if (capability && !hasPlatformCapability(identity.capabilities, capability)) {
    redirect("/admin?error=forbidden");
  }
  return { session, identity };
}
