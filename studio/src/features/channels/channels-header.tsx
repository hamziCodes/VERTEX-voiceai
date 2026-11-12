import { PageHeader } from "@/components/studio/page-header";
import { RouteTabs } from "@/components/studio/route-tabs";

const TABS = [
  { href: "/channels/web", label: "Web" },
  { href: "/channels/telephony", label: "Telephony" },
] as const;

export function ChannelsHeader() {
  return (
    <>
      <PageHeader
        eyebrow="Connect"
        summary="Put a published agent on your website or phone line. Wavia never buys numbers or places calls from this page."
        title="Channels"
      />
      <RouteTabs items={TABS} label="Channels" />
    </>
  );
}
