import { StatePanel } from "@/components/studio/state-panel";

export default function AgentTestLoading() {
  return <StatePanel description="Checking this agent's published version and your test access." title="Loading voice test" tone="loading" />;
}
