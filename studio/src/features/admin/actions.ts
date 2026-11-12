"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { requirePlatform } from "@/auth/platform";
import { ControlPlaneError, controlPlaneRequest } from "@/data/control-plane";
import { platformRoleSchema, platformStaffMemberSchema, supportScopeSchema, supportSessionSchema, type SupportSessionDto } from "@/data/schema";

import {
  LAST_PLATFORM_ADMIN_MESSAGE,
  REASON_MAX_LENGTH,
  REASON_MIN_LENGTH,
  type GrantStaffRoleInput,
  type PlatformStaffMemberDto,
  type RevokeStaffRoleInput,
  type StaffActionResult,
  type EndSupportSessionInput,
  type StartSupportSessionInput,
  type SupportActionResult,
  SUPPORT_DURATIONS,
} from "./types";

const STAFF_PATH = "/admin/staff";

const reasonSchema = z
  .string()
  .transform((value) => value.split(/\s+/).filter(Boolean).join(" "))
  .pipe(z.string().min(REASON_MIN_LENGTH).max(REASON_MAX_LENGTH));
const grantInputSchema = z.strictObject({
  email: z.string().trim().toLowerCase().max(320).pipe(z.email()),
  role: platformRoleSchema,
  reason: reasonSchema,
});
const revokeInputSchema = z.strictObject({ userId: z.uuid(), reason: reasonSchema });

type Failure = Extract<StaffActionResult<never>, { ok: false }>;

function invalid(message: string): Failure {
  return { ok: false, code: "invalid_request", message };
}

function failure(error: unknown): Failure {
  if (error instanceof ControlPlaneError) {
    if (error.status === 409) return { ok: false, code: "last_admin", message: LAST_PLATFORM_ADMIN_MESSAGE };
    if (error.status === 403) return { ok: false, code: "forbidden", message: "Only platform administrators can manage Wavia staff." };
    if (error.status === 404) {
      return { ok: false, code: "not_found", message: "No active Wavia user matches. They must sign in once before a role can be granted." };
    }
    if (error.status === 422) return invalid("The platform service rejected this change. Check the details and try again.");
    return { ok: false, code: "unavailable", message: error.message };
  }
  return { ok: false, code: "unavailable", message: "Staff changes are temporarily unavailable. Try again shortly." };
}

export async function grantStaffRoleAction(input: GrantStaffRoleInput): Promise<StaffActionResult<PlatformStaffMemberDto>> {
  const parsed = grantInputSchema.safeParse(input);
  if (!parsed.success) {
    return invalid(`Enter a valid email, choose a platform role and give a reason of ${REASON_MIN_LENGTH} to ${REASON_MAX_LENGTH} characters.`);
  }
  // Redirects (missing session or capability) must escape before the try block.
  const { session } = await requirePlatform("platform_staff:write");
  try {
    const member = await controlPlaneRequest("/v1/platform/staff", {
      method: "PUT",
      json: parsed.data,
      schema: platformStaffMemberSchema,
      session,
      selectedTenantId: null,
      scope: "platform",
    });
    revalidatePath(STAFF_PATH);
    return { ok: true, data: member };
  } catch (error) {
    return failure(error);
  }
}

export async function revokeStaffRoleAction(input: RevokeStaffRoleInput): Promise<StaffActionResult<null>> {
  const parsed = revokeInputSchema.safeParse(input);
  if (!parsed.success) {
    return invalid(`Give a reason of ${REASON_MIN_LENGTH} to ${REASON_MAX_LENGTH} characters for a valid staff member.`);
  }
  const { session } = await requirePlatform("platform_staff:write");
  try {
    await controlPlaneRequest(`/v1/platform/staff/${parsed.data.userId}/revoke`, {
      method: "POST",
      json: { reason: parsed.data.reason },
      schema: z.null(),
      session,
      selectedTenantId: null,
      scope: "platform",
    });
    revalidatePath(STAFF_PATH);
    return { ok: true, data: null };
  } catch (error) {
    return failure(error);
  }
}

// ── Phase 13K support sessions ─────────────────────────────────────────────

const SUPPORT_PATH = "/admin/support-sessions";
const startSupportSchema = z.strictObject({
  tenantId: z.uuid(),
  reason: reasonSchema,
  reference: z.string().trim().max(64),
  scopes: z.array(supportScopeSchema).min(1).max(2),
  durationMinutes: z.number().int().refine((value) => (SUPPORT_DURATIONS as readonly number[]).includes(value)),
});
const endSupportSchema = z.strictObject({
  sessionId: z.uuid(),
  reason: z.string().transform((value) => value.split(/\s+/).filter(Boolean).join(" ")).pipe(z.union([z.literal(""), z.string().min(REASON_MIN_LENGTH).max(REASON_MAX_LENGTH)])),
});

type SupportFailure = Extract<SupportActionResult<never>, { ok: false }>;

function supportFailure(error: unknown): SupportFailure {
  if (error instanceof ControlPlaneError) {
    if (error.status === 409) return { ok: false, code: "conflict", message: "You already have an active support session for this tenant. Open it from Support sessions." };
    if (error.status === 410) return { ok: false, code: "closed", message: "This support session has already ended or expired." };
    if (error.status === 403) return { ok: false, code: "forbidden", message: "Your platform role cannot do that for this support session." };
    if (error.status === 404) return { ok: false, code: "not_found", message: "That tenant or support session no longer exists." };
    if (error.status === 422) return { ok: false, code: "invalid_request", message: "The platform service rejected this request. Check the details and try again." };
    return { ok: false, code: "unavailable", message: error.message };
  }
  return { ok: false, code: "unavailable", message: "Support sessions are temporarily unavailable. Try again shortly." };
}

export async function startSupportSessionAction(input: StartSupportSessionInput): Promise<SupportActionResult<SupportSessionDto>> {
  const parsed = startSupportSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, code: "invalid_request", message: `Give a reason of ${REASON_MIN_LENGTH} to ${REASON_MAX_LENGTH} characters, choose at least one scope and a duration.` };
  }
  const { session } = await requirePlatform("platform_support_session:write");
  try {
    const created = await controlPlaneRequest(`/v1/platform/tenants/${parsed.data.tenantId}/support-sessions`, {
      method: "POST",
      json: {
        reason: parsed.data.reason,
        reference: parsed.data.reference || null,
        scopes: parsed.data.scopes,
        duration_minutes: parsed.data.durationMinutes,
      },
      schema: supportSessionSchema,
      session,
      selectedTenantId: null,
      scope: "platform",
    });
    revalidatePath(SUPPORT_PATH);
    return { ok: true, data: created };
  } catch (error) {
    return supportFailure(error);
  }
}

export async function endSupportSessionAction(input: EndSupportSessionInput): Promise<SupportActionResult<SupportSessionDto>> {
  const parsed = endSupportSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, code: "invalid_request", message: `Leave the reason empty or give ${REASON_MIN_LENGTH} to ${REASON_MAX_LENGTH} characters.` };
  }
  const { session } = await requirePlatform("platform_support_session:write");
  try {
    const ended = await controlPlaneRequest(`/v1/platform/support-sessions/${parsed.data.sessionId}/end`, {
      method: "POST",
      json: parsed.data.reason ? { reason: parsed.data.reason } : {},
      schema: supportSessionSchema,
      session,
      selectedTenantId: null,
      scope: "platform",
    });
    revalidatePath(SUPPORT_PATH);
    revalidatePath(`${SUPPORT_PATH}/${parsed.data.sessionId}`);
    return { ok: true, data: ended };
  } catch (error) {
    return supportFailure(error);
  }
}
