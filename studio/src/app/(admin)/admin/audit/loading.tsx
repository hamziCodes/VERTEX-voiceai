import { StatePanel } from "@/components/studio/state-panel";

export default function PlatformAuditLoading() {
  return <StatePanel description="Fetching recent platform events." title="Loading platform audit" tone="loading" />;
}
