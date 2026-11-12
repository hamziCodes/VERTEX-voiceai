import { requirePlatform } from "@/auth/platform";
import { PageHeader } from "@/components/studio/page-header";
import { AUDIT_PAGE_SIZE, loadPlatformAudit } from "@/features/admin/data";
import { PlatformAuditView } from "@/features/admin/platform-audit-view";

export default async function AuditPage() {
  const { session } = await requirePlatform("platform_audit:read");
  const events = await loadPlatformAudit(session);

  return (
    <section className="admin-page">
      <PageHeader
        eyebrow="Wavia admin"
        summary="Platform staff changes and tenant summary views. Customer workspace events stay in each workspace's own audit."
        title="Platform audit"
      />
      <PlatformAuditView events={events} limit={AUDIT_PAGE_SIZE} />
    </section>
  );
}
