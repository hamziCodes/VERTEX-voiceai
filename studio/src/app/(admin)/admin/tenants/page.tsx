import { requirePlatform } from "@/auth/platform";
import { PageHeader } from "@/components/studio/page-header";
import { DIRECTORY_MAX_OFFSET, DIRECTORY_PAGE_SIZE, loadTenantDirectory } from "@/features/admin/data";
import { TenantDirectory } from "@/features/admin/tenant-directory";

const MAX_PAGE = Math.floor(DIRECTORY_MAX_OFFSET / DIRECTORY_PAGE_SIZE) + 1;

function parsePage(value: string | undefined): number {
  if (!value || !/^\d{1,4}$/.test(value)) return 1;
  return Math.min(Math.max(Number(value), 1), MAX_PAGE);
}

export default async function TenantsPage({ searchParams }: { searchParams: Promise<{ q?: string; page?: string }> }) {
  const params = await searchParams;
  const { session } = await requirePlatform("platform_tenant:read");
  const query = (params.q ?? "").trim().slice(0, 255) || undefined;
  const page = parsePage(params.page);
  const result = await loadTenantDirectory(session, { q: query, offset: (page - 1) * DIRECTORY_PAGE_SIZE });

  return (
    <section className="admin-page">
      <PageHeader
        eyebrow="Wavia admin"
        summary="Safe tenant metadata only. Customer conversations, transcripts, recordings and credentials are never listed here."
        title="Tenants"
      />
      <TenantDirectory page={page} query={query} result={result} />
    </section>
  );
}
