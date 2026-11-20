import Link from "next/link";
import { notFound } from "next/navigation";

import { hasPlatformCapability, requirePlatform } from "@/auth/platform";
import { PageHeader } from "@/components/studio/page-header";
import { StatePanel } from "@/components/studio/state-panel";
import { ControlPlaneError } from "@/data/control-plane";
import type { SupportConfigurationDto, SupportReadinessDto, SupportSessionDto } from "@/data/schema";
import { endSupportSessionAction } from "@/features/admin/actions";
import { loadSupportConfiguration, loadSupportReadiness, loadSupportSession } from "@/features/admin/data";
import { EndSupportSession } from "@/features/admin/end-support-session";
import {
  SupportConfigurationView,
  SupportReadinessView,
  SupportSessionBanner,
  SupportSessionDetails,
} from "@/features/admin/support-session-views";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function ClosedState({ session, title }: { session: SupportSessionDto; title: string }) {
  return (
    <>
      <StatePanel
        actions={<Link className="button button--secondary" href={`/admin/tenants/${session.tenant_id}`}>Open tenant summary</Link>}
        description="No tenant data is shown once a session closes. Start a new session from the tenant summary if you still need access."
        title={title}
      />
      <SupportSessionDetails session={session} />
    </>
  );
}

export default async function SupportSessionPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = await params;
  if (!UUID_PATTERN.test(sessionId)) notFound();
  const { identity, session } = await requirePlatform("platform_support_session:read");
  let support: SupportSessionDto;
  try {
    support = await loadSupportSession(session, sessionId);
  } catch (error) {
    if (error instanceof ControlPlaneError && error.status === 404) notFound();
    throw error;
  }

  const isOwner = support.actor_user_id === identity.user_id;
  const canEnd = support.state === "active"
    && hasPlatformCapability(identity.capabilities, "platform_support_session:write")
    && (isOwner || hasPlatformCapability(identity.capabilities, "platform_support_session:manage"));
  const header = (
    <>
      <Link className="text-action operate-back" href="/admin/support-sessions">← Support sessions</Link>
      <PageHeader eyebrow="Support session" summary="Read-only view of safe tenant metadata." title={support.tenant_name} />
    </>
  );

  if (support.state !== "active") {
    return (
      <section className="admin-page">
        {header}
        <ClosedState session={support} title={support.state === "expired" ? "Support session expired" : "Support session ended"} />
      </section>
    );
  }

  const banner = (
    <SupportSessionBanner
      actions={canEnd ? <EndSupportSession onEnd={endSupportSessionAction} sessionId={support.session_id} tenantName={support.tenant_name} /> : undefined}
      session={support}
    />
  );

  if (!isOwner) {
    return (
      <section className="admin-page">
        {header}
        {banner}
        <p className="inline-notice inline-notice--info">
          Only {support.actor_email ?? "the staff member who opened it"} can view tenant data in this session.
        </p>
        <SupportSessionDetails session={support} />
      </section>
    );
  }

  // Each load is an audited support read; FastAPI re-checks owner, expiry and scope.
  let configuration: SupportConfigurationDto | null = null;
  let readiness: SupportReadinessDto | null = null;
  try {
    if (support.scopes.includes("configuration")) configuration = await loadSupportConfiguration(session, support.session_id);
    if (support.scopes.includes("readiness")) readiness = await loadSupportReadiness(session, support.session_id);
  } catch (error) {
    if (error instanceof ControlPlaneError && (error.status === 410 || error.status === 403)) {
      return (
        <section className="admin-page">
          {header}
          <ClosedState session={support} title="Support session closed" />
        </section>
      );
    }
    throw error;
  }

  return (
    <section className="admin-page">
      {header}
      {banner}
      <p className="muted-copy support-section__note">Each view of this page is recorded in the platform audit against your account.</p>
      {configuration ? <SupportConfigurationView data={configuration} /> : null}
      {readiness ? <SupportReadinessView data={readiness} /> : null}
      <SupportSessionDetails session={support} />
    </section>
  );
}
