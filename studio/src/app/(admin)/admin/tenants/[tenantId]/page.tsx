import Link from "next/link";
import { notFound } from "next/navigation";

import { requirePlatform } from "@/auth/platform";
import { PageHeader } from "@/components/studio/page-header";
import { ControlPlaneError } from "@/data/control-plane";
import { loadTenantSummary } from "@/features/admin/data";
import { TenantSummaryView } from "@/features/admin/tenant-summary-view";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default async function TenantDetailPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = await params;
  if (!UUID_PATTERN.test(tenantId)) notFound();
  const { session } = await requirePlatform("platform_tenant:read");
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
      <PageHeader eyebrow="Tenant summary" summary="Read-only metadata for support and administration." title={summary.name} />
      <TenantSummaryView summary={summary} />
    </section>
  );
}
