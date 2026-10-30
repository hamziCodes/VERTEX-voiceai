import { z } from "zod";

export const workspaceSummarySchema = z.object({
  id: z.string().uuid(),
  name: z.string().trim().min(1),
  role: z.enum(["tenant_admin", "tenant_editor", "tenant_viewer"]),
});

export function parseControlPlaneDto<T>(
  schema: z.ZodType<T>,
  payload: unknown,
): T {
  return schema.parse(payload);
}
