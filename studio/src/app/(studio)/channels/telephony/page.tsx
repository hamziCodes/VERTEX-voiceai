import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { saveTelephonyPolicyAction } from "@/features/channels/actions";
import { ChannelsHeader } from "@/features/channels/channels-header";
import { getTelephonySettings } from "@/features/channels/data";
import { TelephonyChannelView } from "@/features/channels/telephony-channel-view";

export default async function TelephonyChannelPage() {
  const { membership } = await requireWorkspace("telephony:read");
  const settings = await getTelephonySettings();
  const canEdit = hasWorkspaceCapability(membership.capabilities, "telephony:write");

  return (
    <section className="channels-page">
      <ChannelsHeader />
      <TelephonyChannelView
        settings={settings}
        canEdit={canEdit}
        onSave={saveTelephonyPolicyAction}
      />
    </section>
  );
}
