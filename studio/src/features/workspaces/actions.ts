"use server";

import { getSignInUrl, signOut } from "@workos-inc/authkit-nextjs";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { workspaceCookieSecret } from "@/auth/config";
import { INVITATION_COOKIE_NAME, invitationCookieOptions, sealInvitationToken, unsealInvitationToken } from "@/auth/invitation";
import { requireSession } from "@/auth/session";
import { listCurrentWorkspaces, setSelectedWorkspace } from "@/auth/workspace";
import { ControlPlaneError, controlPlaneRequest } from "@/data/control-plane";
import { workspaceMemberSchema, type WorkspaceMemberDto } from "@/data/schema";

// Mirrors control_plane/routes/identity.py `_membership_error` for invitation acceptance.
const INVITATION_FAILURES: Readonly<Record<number, string>> = {
  403: "invitation-mismatch",
  404: "invalid-invitation",
  409: "invitation-used",
  410: "invitation-expired",
  422: "invalid-invitation",
};

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
  let membership: WorkspaceMemberDto;
  try {
    membership = await controlPlaneRequest("/v1/invitations/accept", {
      method: "POST",
      json: { token },
      schema: workspaceMemberSchema,
      session,
      selectedTenantId: null,
      scope: "identity",
    });
  } catch (error) {
    const outcome = error instanceof ControlPlaneError ? INVITATION_FAILURES[error.status] : undefined;
    if (!outcome) throw error;
    // Terminal outcomes: the token can never succeed, so stop holding it.
    store.delete(INVITATION_COOKIE_NAME);
    redirect(`/workspaces?error=${outcome}`);
  }
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
