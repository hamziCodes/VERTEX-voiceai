import type { TelephonyPolicyDto, TelephonySettingsDto } from "@/data/schema";

export interface AgentSummary {
  agent_id: string;
  name: string;
  is_published: boolean;
}

export type { TelephonyPolicyDto, TelephonySettingsDto };
