import { StatePanel } from "@/components/studio/state-panel";

export default function OperationsLoading() {
  return <StatePanel description="Collecting the control plane's health signals." title="Loading operations" tone="loading" />;
}
