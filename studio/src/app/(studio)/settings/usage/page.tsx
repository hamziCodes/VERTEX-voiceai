import { requireWorkspace } from "@/auth/workspace";
import { OperationsNavigation } from "@/features/operations/operations-navigation";
import { getUsage } from "@/features/usage/data";
import { UsageView } from "@/features/usage/usage-view";

export default async function UsagePage() {
  const { session, membership } = await requireWorkspace("usage:read");
  const usage = await getUsage(session, membership.tenant_id);
  return (
    <>
      <OperationsNavigation capabilities={membership.capabilities} />
      <UsageView usage={usage} />
    </>
  );
}
