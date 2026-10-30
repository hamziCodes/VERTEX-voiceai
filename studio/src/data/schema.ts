import { z } from "zod";

export const workspaceSummarySchema = z.object({
  user_id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  tenant_name: z.string().trim().min(1),
  role: z.enum(["tenant_admin", "tenant_editor", "tenant_viewer", "compliance_admin"]),
  created_at: z.iso.datetime(),
});

export const currentIdentitySchema = z.object({
  user_id: z.string().uuid(),
  email: z.string().email().nullable(),
  is_active: z.boolean(),
  is_platform_admin: z.boolean(),
  memberships: z.array(workspaceSummarySchema),
});

export function parseControlPlaneDto<T>(
  schema: z.ZodType<T>,
  payload: unknown,
): T {
  return schema.parse(payload);
}
