import type { WorkspaceSummaryDto } from "@/data/dto";

export type WorkspaceRole = WorkspaceSummaryDto["role"];
export {
  hasWorkspaceCapability,
  type WorkspaceCapability,
} from "./capabilities";
