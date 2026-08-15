export type ExtractionMode = "realtime" | "final";

export type FieldConfidence = "low" | "medium" | "high";

// Shape returned by the Groq VOB extraction after normalizeExtraction():
// every data field is a trimmed string or null (numbers/booleans are stringified),
// field_confidence maps every non-null field to its confidence level.
export interface ExtractedVobData {
  verification_id: string | null;
  practice_name: string | null;
  patient_full_name: string | null;
  patient_dob: string | null;
  member_id: string | null;
  payer_name: string | null;
  provider_name: string | null;
  provider_npi: string | null;
  tax_id: string | null;
  cpt_codes: string | null;
  service_type: string | null;
  date_of_service: string | null;
  policy_active: string | null;
  plan_type: string | null;
  effective_date: string | null;
  network_status: string | null;
  individual_deductible_total: string | null;
  individual_deductible_met: string | null;
  individual_deductible_remaining: string | null;
  family_deductible_total: string | null;
  family_deductible_met: string | null;
  family_deductible_remaining: string | null;
  individual_oop_total: string | null;
  individual_oop_met: string | null;
  individual_oop_remaining: string | null;
  family_oop_total: string | null;
  family_oop_met: string | null;
  family_oop_remaining: string | null;
  copay: string | null;
  coinsurance: string | null;
  deductible_applies: string | null;
  cpt_coverage: string | null;
  cpt_limitations: string | null;
  visit_limit: string | null;
  visits_used: string | null;
  visits_remaining: string | null;
  prior_auth_required: string | null;
  auth_method: string | null;
  referral_required: string | null;
  claims_mailing_address: string | null;
  electronic_payer_id: string | null;
  representative_name: string | null;
  call_reference_number: string | null;
  status: string | null;
  notes: string | null;
  field_confidence: Record<string, FieldConfidence>;
}

export interface VobExtractionSnapshot {
  call_id: string;
  event: string;
  mode: ExtractionMode;
  extracted_at: string;
  transcript_length: number;
  extraction: ExtractedVobData;
}

// Permissive view of the Retell webhook payload: the handlers probe several
// shapes (top-level, call.*, data.*, data.call.*), so everything is optional
// and unknown-valued where the code stringifies defensively.
export interface RetellCallPayload {
  call_id?: string;
  agent_id?: string;
  agent_name?: string;
  from_number?: string;
  transcript?: unknown;
  transcript_with_tool_calls?: unknown;
  transcript_object?: unknown;
  metadata?: unknown;
  retell_llm_dynamic_variables?: unknown;
  dynamic_variables?: unknown;
  [key: string]: unknown;
}

export interface RetellWebhookPayload {
  event?: string;
  call_id?: string;
  call?: RetellCallPayload;
  transcript?: unknown;
  transcript_with_tool_calls?: unknown;
  transcript_object?: unknown;
  data?: {
    call_id?: string;
    call?: RetellCallPayload;
    transcript?: unknown;
    transcript_with_tool_calls?: unknown;
    transcript_object?: unknown;
    metadata?: unknown;
    retell_llm_dynamic_variables?: unknown;
    dynamic_variables?: unknown;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}
