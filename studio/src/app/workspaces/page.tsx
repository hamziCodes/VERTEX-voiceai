import { cookies } from "next/headers";

import { INVITATION_COOKIE_NAME } from "@/auth/invitation";
import { requireSession } from "@/auth/session";
import { listCurrentWorkspaces } from "@/auth/workspace";
import { acceptPendingInvitationAction, selectWorkspaceAction, signOutAction } from "@/features/workspaces/actions";

export default async function WorkspacesPage() {
  const session = await requireSession();
  const identity = await listCurrentWorkspaces(session);
  const hasInvitation = Boolean((await cookies()).get(INVITATION_COOKIE_NAME));
  return (
    <main>
      <header>
        <p>Signed in as {session.displayName}</p>
        <form action={signOutAction}><button type="submit">Sign out</button></form>
      </header>
      <h1>Choose a workspace</h1>
      {hasInvitation ? (
        <form action={acceptPendingInvitationAction}>
          <p>You have a pending workspace invitation.</p>
          <button type="submit">Accept invitation</button>
        </form>
      ) : null}
      {identity.memberships.length === 0 ? (
        <p>No workspace membership is available yet. Ask an administrator for an invitation.</p>
      ) : (
        <ul>
          {identity.memberships.map((membership) => (
            <li key={membership.tenant_id}>
              <form action={selectWorkspaceAction}>
                <input name="workspaceId" type="hidden" value={membership.tenant_id} />
                <button type="submit">{membership.tenant_name} <span>({membership.role})</span></button>
              </form>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
