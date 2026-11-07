import Link from "next/link";

import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { PageHeader } from "@/components/studio/page-header";
import { StatusBadge } from "@/components/studio/status-badge";
import { loadAgents, loadEntitlements } from "@/features/agents/data";
import { loadOnboarding } from "@/features/onboarding/data";

export default async function DashboardPage() {
  const { session, membership } = await requireWorkspace();
  const [onboarding, agents, entitlements] = await Promise.all([
    loadOnboarding(session, membership.tenant_id),
    loadAgents(session, membership.tenant_id),
    loadEntitlements(session, membership.tenant_id),
  ]);
  const canEditSetup = hasWorkspaceCapability(membership.capabilities, "onboarding:write");
  const canEditAgents = hasWorkspaceCapability(membership.capabilities, "agent:write");
  const canTest = hasWorkspaceCapability(membership.capabilities, "session:mint");
  const publishedAgents = agents.filter((agent) => agent.is_published);
  const firstAgent = agents[0];
  const firstPublished = publishedAgents[0];

  let nextAction: { title: string; description: string; label?: string; href?: string };
  if (onboarding.requirement_codes.length > 0) {
    nextAction = {
      title: "Complete workspace setup",
      description: "Finish the remaining business details before configuring production connections.",
      label: canEditSetup ? "Continue setup" : "Review setup",
      href: "/onboarding",
    };
  } else if (agents.length === 0) {
    nextAction = canEditAgents
      ? {
          title: "Create your first agent",
          description: "Start from a tested template or a clean default configuration.",
          label: "Create agent",
          href: "/agents/new",
        }
      : {
          title: "No agents yet",
          description: "A workspace editor can create the first agent. You will be able to review it here afterward.",
        };
  } else if (!firstPublished) {
    nextAction = {
      title: canEditAgents ? "Finish your first agent" : "Review the agent draft",
      description: canEditAgents
        ? "Complete the draft, check readiness, and publish when its configuration is valid."
        : "This workspace has a draft agent that has not been published yet.",
      label: canEditAgents ? "Open draft" : "View draft",
      href: `/agents/${firstAgent.agent_id}/build`,
    };
  } else if (canTest) {
    nextAction = {
      title: "Test your published agent",
      description: "Open the existing sandbox when you are ready. No provider is contacted until you explicitly start a session.",
      label: "Open test sandbox",
      href: `/agents/${firstPublished.agent_id}/test`,
    };
  } else {
    nextAction = {
      title: "Published agent ready",
      description: "Your workspace has a published agent. Your role can review its configuration but cannot start a test session.",
      label: "View agent",
      href: `/agents/${firstPublished.agent_id}/build`,
    };
  }

  return (
    <section className="dashboard-page">
      <PageHeader
        eyebrow="Workspace overview"
        summary="Continue from the next incomplete step using only your workspace's current configuration."
        title={membership.tenant_name}
      />
      <section className="dashboard-next">
        <div>
          <StatusBadge tone={onboarding.requirement_codes.length > 0 ? "warning" : "success"}>
            {onboarding.requirement_codes.length > 0 ? "Action needed" : "Setup saved"}
          </StatusBadge>
          <h2>{nextAction.title}</h2>
          <p>{nextAction.description}</p>
        </div>
        {nextAction.href && nextAction.label ? <Link className="button button--primary" href={nextAction.href}>{nextAction.label}</Link> : null}
      </section>
      <div aria-label="Workspace readiness" className="readiness-grid">
        <section>
          <span>Workspace setup</span>
          <strong>{onboarding.requirement_codes.length === 0 ? "Complete" : `${onboarding.requirement_codes.length} item${onboarding.requirement_codes.length === 1 ? "" : "s"} remaining`}</strong>
          <Link href="/onboarding">Open setup details</Link>
        </section>
        <section>
          <span>Agents</span>
          <strong>{agents.length} of {entitlements.max_agents}</strong>
          <Link href="/agents">View agents</Link>
        </section>
        <section>
          <span>Published</span>
          <strong>{publishedAgents.length} published</strong>
          <span className="readiness-grid__note">Only published agents can start a test session.</span>
        </section>
      </div>
    </section>
  );
}
