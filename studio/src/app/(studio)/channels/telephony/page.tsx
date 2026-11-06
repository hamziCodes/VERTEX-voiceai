import Link from "next/link";
import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { getTelephonySettings } from "@/features/channels/data";
import { saveTelephonyPolicyAction } from "@/features/channels/actions";
import { TelephonyChannelView } from "@/features/channels/telephony-channel-view";

export default async function TelephonyChannelPage() {
  const { membership } = await requireWorkspace("telephony:read");
  const settings = await getTelephonySettings();
  const canEdit = hasWorkspaceCapability(membership.capabilities, "telephony:write");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <nav aria-label="Channel tabs" style={{ display: "flex", gap: "1rem", borderBottom: "1px solid #e4e4e7", paddingBottom: "0.5rem" }}>
        <Link href="/channels/web" style={{ color: "#71717a", paddingBottom: "0.5rem" }}>
          Web Embed
        </Link>
        <Link href="/channels/telephony" style={{ fontWeight: 600, color: "#18181b", borderBottom: "2px solid #18181b", paddingBottom: "0.5rem" }}>
          Telephony
        </Link>
      </nav>

      <TelephonyChannelView
        settings={settings}
        canEdit={canEdit}
        onSave={saveTelephonyPolicyAction}
      />
    </div>
  );
}
