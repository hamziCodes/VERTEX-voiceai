import { StatePanel } from "@/components/studio/state-panel";

export default function ApiKeysLoading() {
  return <StatePanel description="Checking this workspace's webhook endpoints." title="Loading webhooks" tone="loading" />;
}
