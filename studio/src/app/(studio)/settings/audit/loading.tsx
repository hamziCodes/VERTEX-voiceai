import { StatePanel } from "@/components/studio/state-panel";

export default function AuditLoading() {
  return <StatePanel description="Checking recorded workspace events." title="Loading audit history" tone="loading" />;
}
