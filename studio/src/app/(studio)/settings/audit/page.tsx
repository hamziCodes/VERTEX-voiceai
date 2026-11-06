import { requireWorkspace } from "@/auth/workspace";
import { AuditView } from "@/features/audit/audit-view";
import { getAuditEvents } from "@/features/audit/data";
import { OperationsNavigation } from "@/features/operations/operations-navigation";

export default async function AuditPage() {
  const { session, membership } = await requireWorkspace("audit:read");
  const events = await getAuditEvents(session, membership.tenant_id);
  return (
    <>
      <OperationsNavigation capabilities={membership.capabilities} />
      <AuditView events={events} />
    </>
  );
}
