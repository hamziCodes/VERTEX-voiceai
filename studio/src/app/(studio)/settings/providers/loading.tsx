import { StatePanel } from "@/components/studio/state-panel";

export default function ProvidersLoading() {
  return <StatePanel description="Checking the provider catalog and credential metadata." title="Loading provider credentials" tone="loading" />;
}
