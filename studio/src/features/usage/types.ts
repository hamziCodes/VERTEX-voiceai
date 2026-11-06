export interface UsageDto {
  status: string;
  tenant_id: string;
  quota: {
    max_concurrent: number;
    max_minutes_month: number;
    max_llm_tokens_month?: number;
    current_concurrent: number;
    current_monthly_minutes: number;
    current_monthly_llm_tokens?: number;
    soft_cap_percent?: number;
    hard_cap_percent?: number;
  };
  totals: Record<string, number>;
}
