import { StatePanel } from "@/components/studio/state-panel";

export default function SupportSessionLoading() {
  return <StatePanel description="Checking the session and loading permitted tenant metadata." title="Loading support session" tone="loading" />;
}
