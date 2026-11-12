import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { PageHeader } from "@/components/studio/page-header";
import { revokeProviderCredentialAction, storeProviderCredentialAction } from "@/features/providers/actions";
import { getProviderCatalog, getWorkspaceEntitlements, listProviderCredentials } from "@/features/providers/data";
import { ProviderCredentialManager } from "@/features/providers/provider-credential-manager";

export default async function ProvidersSettingsPage() {
  const { membership } = await requireWorkspace("provider_credential:read");
  const [catalog, credentials, entitlements] = await Promise.all([
    getProviderCatalog(),
    listProviderCredentials(),
    getWorkspaceEntitlements(),
  ]);
  const canManage = hasWorkspaceCapability(membership.capabilities, "provider_credential:write");

  return (
    <section className="developer-page">
      <PageHeader
        eyebrow="Developer"
        summary="Bring your own provider keys for the voice pipeline. Secrets are encrypted at rest and only their metadata is shown here."
        title="AI provider credentials"
      />
      <ProviderCredentialManager
        catalog={catalog}
        credentials={credentials}
        advancedEnabled={entitlements.advanced_providers_enabled}
        canManage={canManage}
        onSave={storeProviderCredentialAction}
        onRevoke={revokeProviderCredentialAction}
      />
    </section>
  );
}
