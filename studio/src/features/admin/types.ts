import type { PlatformRole, PlatformStaffMemberDto } from "@/data/schema";

export type { PlatformRole, PlatformStaffMemberDto };

export const PLATFORM_ROLES = ["platform_admin", "platform_support"] as const satisfies readonly PlatformRole[];

export const PLATFORM_ROLE_DETAILS: Readonly<Record<PlatformRole, { label: string; description: string }>> = {
  platform_admin: {
    label: "Platform administrator",
    description: "Manages Wavia staff roles and reads the tenant directory and platform audit. Holds no customer workspace access.",
  },
  platform_support: {
    label: "Platform support",
    description: "Searches tenants and reads safe tenant summaries. Read-only, with no customer workspace access.",
  },
};

export const LAST_PLATFORM_ADMIN_MESSAGE =
  "Wavia must keep at least one platform administrator. Grant the role to someone else first.";

export const REASON_MIN_LENGTH = 8;
export const REASON_MAX_LENGTH = 500;

export interface GrantStaffRoleInput {
  email: string;
  role: PlatformRole;
  reason: string;
}

export interface RevokeStaffRoleInput {
  userId: string;
  reason: string;
}

export type StaffActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; code: "invalid_request" | "forbidden" | "not_found" | "last_admin" | "unavailable"; message: string };

export const AUDIT_ACTION_LABELS: Readonly<Record<string, string>> = {
  "platform_staff.migrated": "Migrated from legacy flag",
  "platform_staff.granted": "Staff role granted",
  "platform_staff.role_changed": "Staff role changed",
  "platform_staff.revoked": "Staff role revoked",
  "platform_tenant.viewed": "Tenant summary viewed",
};
