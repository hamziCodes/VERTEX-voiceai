import { requireWorkspace } from "@/auth/workspace";
import { PageHeader } from "@/components/studio/page-header";
import { OperationsNavigation } from "@/features/operations/operations-navigation";
import { getUsage } from "@/features/usage/data";
import { UsageView } from "@/features/usage/usage-view";

export default async function UsagePage() {
  const { session, membership } = await requireWorkspace("usage:read");
  const usage = await getUsage(session, membership.tenant_id);
  return (
    <section className="operate-page">
      <PageHeader
        eyebrow="Operate"
        summary="Server-reported session, minute and token usage against this workspace's limits."
        title="Usage and limits"
      />
      <OperationsNavigation capabilities={membership.capabilities} />
      <UsageView usage={usage} />
    </section>
  );
}
