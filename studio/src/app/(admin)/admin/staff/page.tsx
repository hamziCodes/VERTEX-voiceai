import { hasPlatformCapability, requirePlatform } from "@/auth/platform";
import { PageHeader } from "@/components/studio/page-header";
import { grantStaffRoleAction, revokeStaffRoleAction } from "@/features/admin/actions";
import { loadPlatformStaff } from "@/features/admin/data";
import { StaffManager } from "@/features/admin/staff-manager";

export default async function StaffPage() {
  const { identity, session } = await requirePlatform("platform_staff:read");
  const staff = await loadPlatformStaff(session);
  const canManage = hasPlatformCapability(identity.capabilities, "platform_staff:write");

  return (
    <section className="admin-page">
      <PageHeader
        eyebrow="Wavia admin"
        summary="Grant, change and revoke Wavia platform roles. Every change needs a reason and is recorded in the platform audit."
        title="Staff"
      />
      <StaffManager canManage={canManage} currentUserId={identity.user_id} onGrant={grantStaffRoleAction} onRevoke={revokeStaffRoleAction} staff={staff} />
    </section>
  );
}
