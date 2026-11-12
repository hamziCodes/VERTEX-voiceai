import { StatePanel } from "@/components/studio/state-panel";

export default function UsageLoading() {
  return <StatePanel description="Checking server-reported usage and limits." title="Loading usage" tone="loading" />;
}
