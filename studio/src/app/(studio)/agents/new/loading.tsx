import { StatePanel } from "@/components/studio/state-panel";

export default function NewAgentLoading() {
  return <StatePanel description="Loading templates, workspace limits, and available agent slots." title="Preparing agent creation" tone="loading" />;
}
