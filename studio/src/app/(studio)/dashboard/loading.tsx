import { StatePanel } from "@/components/studio/state-panel";

export default function DashboardLoading() {
  return <StatePanel description="Checking setup, agents, and workspace limits." title="Loading workspace overview" tone="loading" />;
}
