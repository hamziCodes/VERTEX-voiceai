import { requireWorkspace } from "@/auth/workspace";
import { PageHeader } from "@/components/studio/page-header";
import { AuditView } from "@/features/audit/audit-view";
import { getAuditEvents } from "@/features/audit/data";
import { OperationsNavigation } from "@/features/operations/operations-navigation";

export default async function AuditPage() {
  const { session, membership } = await requireWorkspace("audit:read");
  const events = await getAuditEvents(session, membership.tenant_id);
  return (
    <section className="operate-page">
      <PageHeader
        eyebrow="Operate"
        summary="Recorded workspace and system events. Network and internal resource identifiers are not shown."
        title="Audit history"
      />
      <OperationsNavigation capabilities={membership.capabilities} />
      <AuditView events={events} />
    </section>
  );
}
