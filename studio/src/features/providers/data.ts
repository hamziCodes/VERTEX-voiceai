import "server-only";

import { controlPlaneRequest } from "@/data/control-plane";
import {
  catalogProviderListSchema,
  providerCredentialListSchema,
  entitlementsSchema,
  type CatalogProviderDto,
  type ProviderCredentialDto,
} from "@/data/schema";
import { requireWorkspace } from "@/auth/workspace";

export async function getProviderCatalog(): Promise<CatalogProviderDto[]> {
  const { session, membership } = await requireWorkspace("agent:read");
  const res = await controlPlaneRequest("/v1/catalog/providers", {
    schema: catalogProviderListSchema,
    session,
    selectedTenantId: membership.tenant_id,
  });
  return res.providers;
}

export async function listProviderCredentials(): Promise<ProviderCredentialDto[]> {
  const { session, membership } = await requireWorkspace("provider_credential:read");
  const res = await controlPlaneRequest("/v1/provider-credentials", {
    schema: providerCredentialListSchema,
    session,
    selectedTenantId: membership.tenant_id,
  });
  return res.credentials;
}

export async function getWorkspaceEntitlements() {
  const { session, membership } = await requireWorkspace("entitlement:read");
  return controlPlaneRequest("/v1/entitlements", {
    schema: entitlementsSchema,
    session,
    selectedTenantId: membership.tenant_id,
  });
}
