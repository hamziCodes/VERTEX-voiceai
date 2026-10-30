import { hasWorkspacePermission, requireWorkspace } from "@/auth/workspace";
import { saveOnboardingAction } from "@/features/onboarding/actions";
import { loadOnboarding } from "@/features/onboarding/data";
import { OnboardingForm } from "@/features/onboarding/onboarding-form";

export default async function OnboardingPage() {
  const { session, membership } = await requireWorkspace("onboarding:read");
  const onboarding = await loadOnboarding(session, membership.tenant_id);
  return (
    <>
      <h1>Workspace setup</h1>
      <p>Tell Wavia how your business operates. Your progress is saved so you can return later.</p>
      <OnboardingForm
        canEdit={hasWorkspacePermission(membership.role, "onboarding:write")}
        initial={onboarding.profile}
        requirementCodes={onboarding.requirement_codes}
        saveAction={saveOnboardingAction}
      />
    </>
  );
}
