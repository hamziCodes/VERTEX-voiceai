export const WORKSPACE_CAPABILITIES = [
  "agent:read",
  "agent:write",
  "session:mint",
  "session:read",
  "usage:read",
  "secret:rotate",
  "audit:read",
  "member:read",
  "member:write",
  "onboarding:read",
  "onboarding:write",
  "entitlement:read",
  "knowledge:read",
  "knowledge:write",
  "extraction:read",
  "extraction:write",
  "alert:read",
  "alert:write",
  "telephony:read",
  "telephony:write",
  "conversation:read",
  "api_key:read",
  "api_key:write",
  "provider_credential:read",
  "provider_credential:write",
  "erasure:execute",
  "legal_hold:manage",
  "compliance:write",
] as const;

export type WorkspaceCapability = (typeof WORKSPACE_CAPABILITIES)[number];

export function hasWorkspaceCapability(
  capabilities: readonly string[],
  required: WorkspaceCapability,
): boolean {
  return capabilities.includes(required);
}
