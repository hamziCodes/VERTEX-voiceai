import type { WorkspaceSummaryDto } from "@/data/dto";

export type WorkspaceRole = WorkspaceSummaryDto["role"];
export type WorkspacePermission =
  | "agent:read" | "agent:write" | "session:mint" | "session:read"
  | "usage:read" | "member:read" | "member:write" | "audit:read"
  | "telephony:read" | "telephony:write" | "conversation:read"
  | "onboarding:read" | "onboarding:write" | "knowledge:read" | "knowledge:write"
  | "secret:rotate" | "api_key:read" | "api_key:write"
  | "provider_credential:read" | "provider_credential:write"
  | "entitlement:read";

const ROLE_PERMISSIONS: Readonly<Record<WorkspaceRole, ReadonlySet<string>>> = {
  tenant_admin: new Set([
    "agent:read", "agent:write", "session:mint", "session:read", "usage:read", "member:read", "member:write", "audit:read",
    "telephony:read", "telephony:write", "conversation:read", "onboarding:read", "onboarding:write", "knowledge:read", "knowledge:write",
    "secret:rotate", "api_key:read", "api_key:write", "provider_credential:read", "provider_credential:write", "entitlement:read",
  ]),
  tenant_editor: new Set([
    "agent:read", "agent:write", "session:mint", "session:read", "usage:read", "member:read", "audit:read",
    "telephony:read", "conversation:read", "onboarding:read", "onboarding:write", "knowledge:read", "knowledge:write", "entitlement:read",
  ]),
  tenant_viewer: new Set(["agent:read", "session:read", "usage:read", "conversation:read", "onboarding:read", "knowledge:read", "entitlement:read"]),
  compliance_admin: new Set(["audit:read", "conversation:read", "entitlement:read"]),
};

export function hasWorkspacePermission(role: WorkspaceRole, permission: WorkspacePermission): boolean {
  return ROLE_PERMISSIONS[role].has(permission);
}
