"use server";

import { getSignInUrl, signOut } from "@workos-inc/authkit-nextjs";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { workspaceCookieSecret } from "@/auth/config";
import { INVITATION_COOKIE_NAME, invitationCookieOptions, sealInvitationToken, unsealInvitationToken } from "@/auth/invitation";
import { requireSession } from "@/auth/session";
import { listCurrentWorkspaces, setSelectedWorkspace } from "@/auth/workspace";
import { controlPlaneRequest } from "@/data/control-plane";
import { workspaceSummarySchema } from "@/data/schema";

function formValue(formData: FormData, name: string): string {
  const value = formData.get(name);
  return typeof value === "string" ? value.trim() : "";
}

export async function startSignInAction(formData: FormData): Promise<never> {
  const invitation = formValue(formData, "invitation");
  if (invitation) {
    const store = await cookies();
    store.set(INVITATION_COOKIE_NAME, sealInvitationToken(invitation, workspaceCookieSecret()), invitationCookieOptions());
  }
  redirect(await getSignInUrl({ returnTo: "/workspaces" }));
}

export async function selectWorkspaceAction(formData: FormData): Promise<never> {
  const workspaceId = formValue(formData, "workspaceId");
  const session = await requireSession();
  const identity = await listCurrentWorkspaces(session);
  if (!identity.memberships.some((membership) => membership.tenant_id === workspaceId)) {
    redirect("/workspaces?error=invalid-workspace");
  }
  await setSelectedWorkspace(workspaceId);
  redirect("/dashboard");
}

export async function acceptPendingInvitationAction(): Promise<never> {
  const store = await cookies();
  const sealed = store.get(INVITATION_COOKIE_NAME)?.value;
  const token = sealed ? unsealInvitationToken(sealed, workspaceCookieSecret()) : null;
  if (!token) {
    store.delete(INVITATION_COOKIE_NAME);
    redirect("/workspaces?error=invalid-invitation");
  }
  const session = await requireSession();
  const membership = await controlPlaneRequest("/v1/invitations/accept", {
    method: "POST",
    json: { token },
    schema: workspaceSummarySchema,
    session,
    selectedTenantId: null,
    scope: "identity",
  });
  store.delete(INVITATION_COOKIE_NAME);
  await setSelectedWorkspace(membership.tenant_id);
  redirect("/dashboard");
}

export async function signOutAction(): Promise<void> {
  const store = await cookies();
  store.delete(INVITATION_COOKIE_NAME);
  store.delete("wavia-workspace");
  await signOut({ returnTo: "/sign-in" });
}
