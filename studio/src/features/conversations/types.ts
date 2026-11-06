export interface ConversationSummaryDto {
  call_id: string;
  agent_id: string;
  started_at: string;
  ended_at: string | null;
  transport_type: string;
  disposition: string;
  recording_state: string;
  turn_count: number;
}

export interface ConversationPageDto {
  items: ConversationSummaryDto[];
  next_cursor: string | null;
}

export interface ConversationTurnDto {
  speaker: string;
  text: string;
  start_ms: number;
  end_ms: number;
  language: string;
  confidence: number;
}

export interface RecordingViewDto {
  state: string;
  access: string;
  duration_sec?: number;
  error_code?: string | null;
}

export interface ConversationDetailDto extends ConversationSummaryDto {
  end_reason: string | null;
  transcript: ConversationTurnDto[];
  usage: Record<string, number>;
  recording: RecordingViewDto;
}

export interface IntelligenceResultDto {
  result_id: string;
  call_id: string;
  extraction: Record<string, unknown> | null;
  summary: Record<string, unknown> | null;
  verification_issue_codes: string[];
  created_at: string;
}

export interface ReviewDto {
  review_id: string;
  call_id: string;
  result_id: string;
  reasons: string[];
  state: string;
  decided_by: string | null;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface ConversationIntelligenceDto {
  state: string;
  result: IntelligenceResultDto | null;
  review: ReviewDto | null;
}
