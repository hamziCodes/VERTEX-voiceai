"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { requireWorkspace } from "@/auth/workspace";
import { ControlPlaneError, controlPlaneRequest } from "@/data/control-plane";
import { createdInvitationSchema, studioRoleSchema, workspaceMemberSchema } from "@/data/schema";

import {
  LAST_ADMIN_MESSAGE,
  type ChangeMemberRoleInput,
  type InvitationRevealDto,
  type InviteMemberInput,
  type MemberActionResult,
  type RemoveMemberInput,
  type WorkspaceMemberDto,
} from "./types";

const MEMBERS_PATH = "/settings/members";

const inviteInputSchema = z.strictObject({
  email: z.string().trim().toLowerCase().max(320).pipe(z.email()),
  role: studioRoleSchema,
});
const memberInputSchema = z.strictObject({ userId: z.uuid() });
const roleChangeInputSchema = z.strictObject({ userId: z.uuid(), role: studioRoleSchema });

type Failure = Extract<MemberActionResult<never>, { ok: false }>;

function invalid(message: string): Failure {
  return { ok: false, code: "invalid_request", message };
}

function failure(error: unknown, mutation: "invite" | "member"): Failure {
  if (error instanceof ControlPlaneError) {
    // FastAPI maps LastAdminError to 409 on role change and removal; invitations never 409.
    if (error.status === 409 && mutation === "member") return { ok: false, code: "last_admin", message: LAST_ADMIN_MESSAGE };
    if (error.status === 403) return { ok: false, code: "forbidden", message: "Only workspace administrators can manage members." };
    if (error.status === 404) return { ok: false, code: "not_found", message: "That member is no longer in this workspace. Refresh the list." };
    if (error.status === 422) return invalid("The workspace service rejected this change. Check the details and try again.");
    return { ok: false, code: "unavailable", message: error.message };
  }
  return { ok: false, code: "unavailable", message: "Member changes are temporarily unavailable. Try again shortly." };
}

export async function inviteMemberAction(input: InviteMemberInput): Promise<MemberActionResult<InvitationRevealDto>> {
  const parsed = inviteInputSchema.safeParse(input);
  if (!parsed.success) return invalid("Enter a valid email address and choose one of the five workspace roles.");
  // Redirects (missing session/workspace/capability) must escape before the try block.
  const { session, membership } = await requireWorkspace("member:write");
  try {
    const invitation = await controlPlaneRequest(`/v1/organizations/${membership.tenant_id}/invitations`, {
      method: "POST",
      json: { email: parsed.data.email, role: parsed.data.role },
      schema: createdInvitationSchema,
      session,
      selectedTenantId: membership.tenant_id,
    });
    // The raw token is never logged, persisted or listed: it leaves the server only inside this one-time link.
    return {
      ok: true,
      data: {
        email: invitation.email,
        role: invitation.role,
        expiresAt: invitation.expires_at,
        invitationPath: `/sign-in?invitation=${encodeURIComponent(invitation.token)}`,
      },
    };
  } catch (error) {
    return failure(error, "invite");
  }
}

export async function changeMemberRoleAction(input: ChangeMemberRoleInput): Promise<MemberActionResult<WorkspaceMemberDto>> {
  const parsed = roleChangeInputSchema.safeParse(input);
  if (!parsed.success) return invalid("Choose one of the five workspace roles for a valid member.");
  const { session, membership } = await requireWorkspace("member:write");
  try {
    const updated = await controlPlaneRequest(`/v1/organizations/${membership.tenant_id}/members/${parsed.data.userId}`, {
      method: "PATCH",
      json: { role: parsed.data.role },
      schema: workspaceMemberSchema,
      session,
      selectedTenantId: membership.tenant_id,
    });
    revalidatePath(MEMBERS_PATH);
    return { ok: true, data: updated };
  } catch (error) {
    return failure(error, "member");
  }
}

export async function removeMemberAction(input: RemoveMemberInput): Promise<MemberActionResult<null>> {
  const parsed = memberInputSchema.safeParse(input);
  if (!parsed.success) return invalid("That member reference is not valid.");
  const { session, membership } = await requireWorkspace("member:write");
  try {
    await controlPlaneRequest(`/v1/organizations/${membership.tenant_id}/members/${parsed.data.userId}`, {
      method: "DELETE",
      schema: z.null(),
      session,
      selectedTenantId: membership.tenant_id,
    });
    revalidatePath(MEMBERS_PATH);
    return { ok: true, data: null };
  } catch (error) {
    return failure(error, "member");
  }
}
