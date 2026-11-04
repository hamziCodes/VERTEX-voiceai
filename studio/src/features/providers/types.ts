import type { CatalogProviderDto, ProviderCredentialDto } from "@/data/schema";

export type { CatalogProviderDto, ProviderCredentialDto };

export interface StoreCredentialInput {
  provider_id: string;
  secret: string;
  credential_type?: string;
  reference?: string;
}
