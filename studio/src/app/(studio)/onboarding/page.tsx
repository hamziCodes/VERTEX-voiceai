import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { PageHeader } from "@/components/studio/page-header";
import { saveOnboardingAction } from "@/features/onboarding/actions";
import { loadOnboarding } from "@/features/onboarding/data";
import { OnboardingForm } from "@/features/onboarding/onboarding-form";

export default async function OnboardingPage() {
  const { session, membership } = await requireWorkspace("onboarding:read");
  const onboarding = await loadOnboarding(session, membership.tenant_id);
  return (
    <section className="guided-page">
      <PageHeader
        eyebrow="Setup"
        summary="Tell Wavia how your business operates. Your saved profile is used to guide agent configuration."
        title="Workspace setup"
      />
      <OnboardingForm
        canEdit={hasWorkspaceCapability(membership.capabilities, "onboarding:write")}
        initial={onboarding.profile}
        requirementCodes={onboarding.requirement_codes}
        saveAction={saveOnboardingAction}
      />
    </section>
  );
}
