import { StatePanel } from "@/components/studio/state-panel";

export default function ApiKeysLoading() {
  return <StatePanel description="Checking this workspace's API keys." title="Loading API keys" tone="loading" />;
}
