import type { z } from "zod";

import type { workspaceSummarySchema } from "./schema";

export type WorkspaceSummaryDto = z.infer<typeof workspaceSummarySchema>;

export interface StudioServerSession {
  accessToken: string;
}
