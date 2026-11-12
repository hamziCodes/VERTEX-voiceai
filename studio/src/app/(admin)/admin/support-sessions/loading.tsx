import { StatePanel } from "@/components/studio/state-panel";

export default function SupportSessionsLoading() {
  return <StatePanel description="Fetching active and recent support sessions." title="Loading support sessions" tone="loading" />;
}
