import "server-only";

import { createHmac, timingSafeEqual } from "node:crypto";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { controlPlaneRequest } from "@/data/control-plane";
import type { CurrentIdentityDto, WorkspaceSummaryDto } from "@/data/dto";
import { currentIdentitySchema } from "@/data/schema";

import { workspaceCookieSecret } from "./config";
import { requireSession, type StudioSession } from "./session";
import {
  hasWorkspaceCapability,
  type WorkspaceCapability,
} from "./workspace-permissions";

export {
  hasWorkspaceCapability,
  type WorkspaceCapability,
  type WorkspaceRole,
} from "./workspace-permissions";

export const WORKSPACE_COOKIE_NAME = "wavia-workspace";
const COOKIE_VERSION = "v1";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30;


function signature(payload: string, secret: string): Buffer {
  return createHmac("sha256", secret).update(`wavia:selected-workspace:${payload}`).digest();
}

export function signWorkspaceSelection(workspaceId: string, secret: string): string {
  const payload = Buffer.from(workspaceId, "utf8").toString("base64url");
  return `${COOKIE_VERSION}.${payload}.${signature(payload, secret).toString("base64url")}`;
}

export function verifyWorkspaceSelection(value: string, secret: string): string | null {
  const [version, payload, signatureValue, extra] = value.split(".");
  if (version !== COOKIE_VERSION || !payload || !signatureValue || extra) return null;
  try {
    const supplied = Buffer.from(signatureValue, "base64url");
    const expected = signature(payload, secret);
    if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) return null;
    const workspaceId = Buffer.from(payload, "base64url").toString("utf8");
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(workspaceId)
      ? workspaceId
      : null;
  } catch {
    return null;
  }
}

export function workspaceCookieOptions(secure = process.env.NODE_ENV === "production") {
  return { httpOnly: true as const, sameSite: "lax" as const, secure, path: "/" as const, maxAge: COOKIE_MAX_AGE_SECONDS };
}

export interface WorkspaceContext {
  session: StudioSession;
  identity: CurrentIdentityDto;
  membership: WorkspaceSummaryDto;
}

export async function listCurrentWorkspaces(session: StudioSession): Promise<CurrentIdentityDto> {
  return controlPlaneRequest("/v1/me", {
    schema: currentIdentitySchema,
    session,
    selectedTenantId: null,
    scope: "identity",
  });
}

export async function setSelectedWorkspace(workspaceId: string): Promise<void> {
  const store = await cookies();
  store.set(WORKSPACE_COOKIE_NAME, signWorkspaceSelection(workspaceId, workspaceCookieSecret()), workspaceCookieOptions());
}

export async function clearSelectedWorkspace(): Promise<void> {
  const store = await cookies();
  store.delete(WORKSPACE_COOKIE_NAME);
}

export async function requireWorkspace(capability?: WorkspaceCapability): Promise<WorkspaceContext> {
  const session = await requireSession();
  const identity = await listCurrentWorkspaces(session);
  const store = await cookies();
  const raw = store.get(WORKSPACE_COOKIE_NAME)?.value;
  const selectedId = raw ? verifyWorkspaceSelection(raw, workspaceCookieSecret()) : null;
  const membership = identity.memberships.find((item) => item.tenant_id === selectedId);
  if (!membership) {
    redirect("/workspaces");
  }
  if (capability && !hasWorkspaceCapability(membership.capabilities, capability)) {
    redirect("/workspaces?error=forbidden");
  }
  return { session, identity, membership };
}
