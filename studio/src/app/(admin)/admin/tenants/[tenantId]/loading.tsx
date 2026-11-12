import { StatePanel } from "@/components/studio/state-panel";

export default function TenantDetailLoading() {
  return <StatePanel description="Fetching safe tenant metadata." title="Loading tenant summary" tone="loading" />;
}
