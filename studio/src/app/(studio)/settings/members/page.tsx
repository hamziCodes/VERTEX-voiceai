import Link from "next/link";

import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { PageHeader } from "@/components/studio/page-header";
import { changeMemberRoleAction, inviteMemberAction, removeMemberAction } from "@/features/members/actions";
import { loadWorkspaceMembers } from "@/features/members/data";
import { MemberManager } from "@/features/members/member-manager";

export default async function MembersPage() {
  const { session, membership } = await requireWorkspace("member:read");
  const members = await loadWorkspaceMembers(session, membership.tenant_id);
  const canManage = hasWorkspaceCapability(membership.capabilities, "member:write");

  return (
    <section className="members-page">
      <Link className="text-action members-page__back" href="/settings">← Settings</Link>
      <PageHeader
        eyebrow="Workspace settings"
        summary={canManage
          ? "Invite people with one of the five workspace roles, change roles and remove access. Every change is checked again by the workspace service."
          : "Review who can access this workspace and what each role can do."}
        title="Members"
      />
      <MemberManager
        canManage={canManage}
        currentUserId={membership.user_id}
        members={members}
        onChangeRole={changeMemberRoleAction}
        onInvite={inviteMemberAction}
        onRemove={removeMemberAction}
        workspaceName={membership.tenant_name}
      />
    </section>
  );
}
