import type { z } from "zod";

import type { currentIdentitySchema, workspaceSummarySchema } from "./schema";

export type WorkspaceSummaryDto = z.infer<typeof workspaceSummarySchema>;
export type CurrentIdentityDto = z.infer<typeof currentIdentitySchema>;

export interface StudioServerSession {
  accessToken: string;
}
