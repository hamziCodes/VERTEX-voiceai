import Link from "next/link";
import { notFound } from "next/navigation";

import { hasPlatformCapability, requirePlatform } from "@/auth/platform";
import { PageHeader } from "@/components/studio/page-header";
import { ControlPlaneError } from "@/data/control-plane";
import { startSupportSessionAction } from "@/features/admin/actions";
import { loadTenantSummary } from "@/features/admin/data";
import { StartSupportSession } from "@/features/admin/start-support-session";
import { TenantSummaryView } from "@/features/admin/tenant-summary-view";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default async function TenantDetailPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = await params;
  if (!UUID_PATTERN.test(tenantId)) notFound();
  const { identity, session } = await requirePlatform("platform_tenant:read");
  const canStart = hasPlatformCapability(identity.capabilities, "platform_support_session:write");
  let summary;
  try {
    summary = await loadTenantSummary(session, tenantId);
  } catch (error) {
    if (error instanceof ControlPlaneError && error.status === 404) notFound();
    throw error;
  }

  return (
    <section className="admin-page">
      <Link className="text-action operate-back" href="/admin/tenants">← Back to tenants</Link>
      <PageHeader
        actions={canStart ? <StartSupportSession onStart={startSupportSessionAction} tenantId={summary.tenant_id} tenantName={summary.name} /> : undefined}
        eyebrow="Tenant summary"
        summary="Read-only metadata for support and administration."
        title={summary.name}
      />
      <TenantSummaryView summary={summary} />
    </section>
  );
}
