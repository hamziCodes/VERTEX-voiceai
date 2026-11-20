import { cookies } from "next/headers";
import Link from "next/link";

import { INVITATION_COOKIE_NAME } from "@/auth/invitation";
import { requireSession } from "@/auth/session";
import { listCurrentWorkspaces } from "@/auth/workspace";
import { FormField } from "@/components/studio/form-field";
import { PageHeader } from "@/components/studio/page-header";
import { StatePanel } from "@/components/studio/state-panel";
import { StatusBadge } from "@/components/studio/status-badge";
import { acceptPendingInvitationAction, createWorkspaceAction, selectWorkspaceAction, signOutAction } from "@/features/workspaces/actions";

interface WorkspacesPageProps {
  searchParams: Promise<{ error?: string }>;
}

const ERROR_MESSAGES: Record<string, string> = {
  forbidden: "You do not have permission to open that area.",
  "invalid-invitation": "That invitation is invalid or has expired.",
  "invitation-expired": "This invitation has expired. Ask a workspace administrator to send a new one.",
  "invitation-mismatch": "This invitation was sent to a different email address. Sign in with the invited address.",
  "invitation-used": "This invitation has already been used. If that was not you, tell your workspace administrator.",
  "invalid-workspace": "That workspace is not available to your account.",
  "invalid-workspace-name": "Enter a workspace name of up to 120 characters.",
};

function CreateWorkspaceForm({ first }: { first: boolean }) {
  return (
    <form action={createWorkspaceAction} className="invitation-panel create-workspace">
      <div>
        <h2>{first ? "Create your workspace" : "Create another workspace"}</h2>
        <p>{first
          ? "A workspace holds your agents, knowledge, numbers and conversations. You become its administrator and can invite your team."
          : "Each workspace keeps its own agents, data, members and usage."}</p>
      </div>
      <FormField hint="Shown to everyone you invite." label="Workspace name" name={first ? "workspace-name" : "workspace-name-another"}>
        <input autoComplete="organization" maxLength={120} name="name" placeholder="Acme Clinics" required type="text" />
      </FormField>
      <button className="button button--primary" type="submit">Create workspace</button>
    </form>
  );
}

const ROLE_LABELS: Record<string, string> = {
  tenant_admin: "Administrator",
  tenant_editor: "Editor",
  tenant_developer: "Developer",
  tenant_viewer: "Read-only operator",
  compliance_admin: "Compliance administrator",
};

export default async function WorkspacesPage({ searchParams }: WorkspacesPageProps) {
  const { error = "" } = await searchParams;
  const session = await requireSession();
  const identity = await listCurrentWorkspaces(session);
  const hasInvitation = Boolean((await cookies()).get(INVITATION_COOKIE_NAME));
  return (
    <main className="workspace-entry">
      <div className="workspace-entry__topbar">
        <div className="entry-wordmark"><span aria-hidden="true">W</span> Wavia Studio</div>
        <div className="workspace-entry__account">
          <span>Signed in as <strong>{session.displayName}</strong></span>
          <form action={signOutAction}><button className="button button--secondary" type="submit">Sign out</button></form>
        </div>
      </div>
      <div className="workspace-entry__content">
        <PageHeader eyebrow="Workspace access" title="Choose a workspace" summary="Your role and permissions are specific to each workspace." />
        {error && ERROR_MESSAGES[error] ? (
          <div className="inline-notice inline-notice--danger" role="alert">{ERROR_MESSAGES[error]}</div>
        ) : null}
        {identity.platform_capabilities.length > 0 ? (
          <section aria-labelledby="internal-area-heading" className="invitation-panel admin-entry">
            <div>
              <StatusBadge tone="info">Wavia staff</StatusBadge>
              <h2 id="internal-area-heading">Internal area</h2>
              <p>Your platform role opens the internal Wavia area. It does not open customer workspaces.</p>
            </div>
            <Link className="button button--secondary" href="/admin">Open Wavia admin</Link>
          </section>
        ) : null}
        {hasInvitation ? (
          <form action={acceptPendingInvitationAction} className="invitation-panel">
            <div>
              <StatusBadge tone="info">Invitation ready</StatusBadge>
              <h2>Join a workspace</h2>
              <p>A workspace administrator invited this account. Accept to add the membership.</p>
            </div>
            <button className="button button--primary" type="submit">Accept invitation</button>
          </form>
        ) : null}
        {identity.memberships.length === 0 ? (
          <>
            <StatePanel
              description="Create a workspace to start building, or ask a workspace administrator to invite this account. If you already have an invitation, open its original link and sign in again."
              title="No workspace access yet"
            />
            <CreateWorkspaceForm first />
          </>
        ) : (
          <ul aria-label="Available workspaces" className="workspace-list">
            {identity.memberships.map((membership) => (
              <li key={membership.tenant_id}>
                <form action={selectWorkspaceAction}>
                  <input name="workspaceId" type="hidden" value={membership.tenant_id} />
                  <button className="workspace-choice" type="submit">
                    <span aria-hidden="true" className="workspace-choice__mark">{membership.tenant_name.slice(0, 1).toUpperCase()}</span>
                    <span className="workspace-choice__copy">
                      <strong>{membership.tenant_name}</strong>
                      <span>{ROLE_LABELS[membership.role] ?? "Workspace member"}</span>
                    </span>
                    <span aria-hidden="true" className="workspace-choice__arrow">→</span>
                  </button>
                </form>
              </li>
            ))}
          </ul>
        )}
        {identity.memberships.length > 0 ? (
          <details className="create-workspace-disclosure">
            <summary>Create another workspace</summary>
            <CreateWorkspaceForm first={false} />
          </details>
        ) : null}
      </div>
    </main>
  );
}
