import { StatePanel } from "@/components/studio/state-panel";

export default function MembersLoading() {
  return <StatePanel description="Checking who has access to this workspace." title="Loading members" tone="loading" />;
}
