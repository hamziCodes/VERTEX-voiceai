import type { APIKeyDto } from "@/data/schema";

export type { APIKeyDto };

export interface CreateAPIKeyInput {
  name: string;
  role: "tenant_viewer" | "tenant_editor";
  scopes: string[];
  expires_at?: string | null;
}
