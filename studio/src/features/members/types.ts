import type { StudioRole, WorkspaceMemberDto } from "@/data/schema";

export type { StudioRole, WorkspaceMemberDto };

/** Exactly the five launch customer roles, in the order Studio offers them. */
export const LAUNCH_ROLES = [
  "tenant_admin",
  "tenant_editor",
  "tenant_developer",
  "tenant_viewer",
  "compliance_admin",
] as const satisfies readonly StudioRole[];

export const ROLE_DETAILS: Readonly<Record<StudioRole, { label: string; description: string }>> = {
  tenant_admin: {
    label: "Administrator",
    description: "Owns the workspace: members, API keys, provider credentials, telephony policy, agents and audit.",
  },
  tenant_editor: {
    label: "Editor",
    description: "Builds, tests and publishes agents and knowledge. Cannot manage members or credentials.",
  },
  tenant_developer: {
    label: "Developer",
    description: "Integrates the SDK: tests published agents, manages API keys and reads provider metadata.",
  },
  tenant_viewer: {
    label: "Read-only operator",
    description: "Reviews agents, knowledge, conversations and usage without changing anything.",
  },
  compliance_admin: {
    label: "Compliance administrator",
    description: "Reviews conversations and audit evidence and runs compliance workflows. Cannot edit agents.",
  },
};

export const ADMIN_GRANT_WARNING =
  "Administrators can invite and remove members, change any role, and manage API keys, provider credentials and telephony policy. Grant this only to people who are responsible for the workspace.";

export const LAST_ADMIN_MESSAGE =
  "A workspace must keep at least one administrator. Promote another member first.";

export interface InviteMemberInput {
  email: string;
  role: StudioRole;
}

export interface ChangeMemberRoleInput {
  userId: string;
  role: StudioRole;
}

export interface RemoveMemberInput {
  userId: string;
}

/** Returned once to the inviting administrator; the token lives only inside invitationPath. */
export interface InvitationRevealDto {
  email: string;
  role: StudioRole;
  expiresAt: string;
  invitationPath: string;
}

export type MemberActionErrorCode = "forbidden" | "invalid_request" | "last_admin" | "not_found" | "unavailable";

export type MemberActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; code: MemberActionErrorCode; message: string };
