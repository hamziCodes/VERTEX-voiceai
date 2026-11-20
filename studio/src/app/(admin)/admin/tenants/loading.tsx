import { StatePanel } from "@/components/studio/state-panel";

export default function TenantsLoading() {
  return <StatePanel description="Fetching the tenant directory." title="Loading tenants" tone="loading" />;
}
