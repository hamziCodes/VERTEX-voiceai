import { StatePanel } from "@/components/studio/state-panel";

export default function TelephonyLoading() {
  return <StatePanel description="Checking trunk readiness and calling policy." title="Loading telephony" tone="loading" />;
}
