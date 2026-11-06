import { hasWorkspaceCapability, requireWorkspace } from "@/auth/workspace";
import { getProviderCatalog, listProviderCredentials, getWorkspaceEntitlements } from "@/features/providers/data";
import { storeProviderCredentialAction, revokeProviderCredentialAction } from "@/features/providers/actions";
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
    <ProviderCredentialManager
      catalog={catalog}
      credentials={credentials}
      advancedEnabled={entitlements.advanced_providers_enabled}
      canManage={canManage}
      onSave={storeProviderCredentialAction}
      onRevoke={revokeProviderCredentialAction}
    />
  );
}
