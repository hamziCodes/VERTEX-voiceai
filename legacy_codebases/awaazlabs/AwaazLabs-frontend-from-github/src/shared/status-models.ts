/**
 * CANONICAL STATUS MODELS — spec §17 (Appendix A), implemented verbatim.
 *
 * FROZEN FILE. Declared exactly once; imported everywhere else.
 *
 * Guide Part A Rule 5: "Canonical enums are declared exactly once. Every other file
 * imports from it. Grep for hardcoded status strings in review — any duplicate enum
 * declaration is a defect."
 *
 * Do not add a status that the spec does not list. Do not paraphrase a label.
 * Do not re-declare any of these unions in a feature file.
 */

/* ------------------------------------------------------------------------------------
 * Appointment — §17: booked > confirmed > (rescheduled loops to confirmed)
 *                     > completed | cancelled | no_show
 * ---------------------------------------------------------------------------------- */

export const APPOINTMENT_STATUSES = [
  'booked',
  'confirmed',
  'rescheduled',
  'completed',
  'cancelled',
  'no_show',
] as const;
export type AppointmentStatus = (typeof APPOINTMENT_STATUSES)[number];

export const APPOINTMENT_STATUS_LABELS: Readonly<Record<AppointmentStatus, string>> = {
  booked: 'Booked',
  confirmed: 'Confirmed',
  rescheduled: 'Rescheduled',
  completed: 'Completed',
  cancelled: 'Cancelled',
  no_show: 'No-show',
};

/** Legal next states. `rescheduled` loops back to `confirmed` per §17. */
export const APPOINTMENT_TRANSITIONS: Readonly<Record<AppointmentStatus, readonly AppointmentStatus[]>> = {
  booked: ['confirmed', 'rescheduled', 'cancelled', 'no_show', 'completed'],
  confirmed: ['rescheduled', 'completed', 'cancelled', 'no_show'],
  rescheduled: ['confirmed', 'cancelled'],
  completed: [],
  cancelled: [],
  no_show: [],
};

/* ------------------------------------------------------------------------------------
 * VOB — §7.3 / §17
 *   queued > in_progress (dialing, on_call, pending_callback) > terminal
 * "Everything terminal other than verified is a needs-attention state and appears in
 *  the VOB Queue worklist." (§7.3)
 * ---------------------------------------------------------------------------------- */

export const VOB_IN_PROGRESS_STATUSES = ['dialing', 'on_call', 'pending_callback'] as const;
export type VobInProgressStatus = (typeof VOB_IN_PROGRESS_STATUSES)[number];

export const VOB_TERMINAL_STATUSES = [
  'verified',
  'partial_coverage',
  'needs_authorization',
  'needs_referral',
  'not_covered',
  'inactive_policy',
  'member_not_found',
  'unable_to_verify',
] as const;
export type VobTerminalStatus = (typeof VOB_TERMINAL_STATUSES)[number];

export const VOB_STATUSES = ['queued', ...VOB_IN_PROGRESS_STATUSES, ...VOB_TERMINAL_STATUSES] as const;
export type VobStatus = (typeof VOB_STATUSES)[number];

export const VOB_STATUS_LABELS: Readonly<Record<VobStatus, string>> = {
  queued: 'Queued',
  dialing: 'Dialing',
  on_call: 'On call with payer',
  pending_callback: 'Pending callback',
  verified: 'Verified',
  partial_coverage: 'Partial coverage',
  needs_authorization: 'Needs authorization',
  needs_referral: 'Needs referral',
  not_covered: 'Not covered',
  inactive_policy: 'Inactive policy',
  member_not_found: 'Member not found',
  unable_to_verify: 'Unable to verify',
};

/**
 * §4.2 "Needs attention (sum of unable to verify, member not found, inactive policy;
 * red accent)". This is the Overview card's narrower definition — NOT the same set as
 * `isVobNeedsAttention`, which is the §7.3 worklist definition. They differ, and the
 * spec means both. Keep them distinct.
 */
export const VOB_OVERVIEW_NEEDS_ATTENTION_STATUSES = [
  'unable_to_verify',
  'member_not_found',
  'inactive_policy',
] as const satisfies readonly VobTerminalStatus[];

export function isVobTerminal(status: VobStatus): status is VobTerminalStatus {
  return (VOB_TERMINAL_STATUSES as readonly string[]).includes(status);
}

export function isVobInProgress(status: VobStatus): status is VobInProgressStatus {
  return (VOB_IN_PROGRESS_STATUSES as readonly string[]).includes(status);
}

/** §7.3: terminal and not `verified` => appears in the VOB Queue worklist. */
export function isVobNeedsAttention(status: VobStatus): boolean {
  return isVobTerminal(status) && status !== 'verified';
}

/** §4.2: the Overview "Needs attention" card counts only these three. */
export function isVobOverviewNeedsAttention(status: VobStatus): boolean {
  return (VOB_OVERVIEW_NEEDS_ATTENTION_STATUSES as readonly string[]).includes(status);
}

/**
 * §5.2 Appointments table: "VOB status chip (Verified, Partial, Needs auth,
 * Needs referral, Not covered, or none)". The chip uses these abbreviated labels;
 * they are a display concern of that column only, not a separate status model.
 */
export const VOB_CHIP_LABELS: Readonly<Partial<Record<VobStatus, string>>> = {
  verified: 'Verified',
  partial_coverage: 'Partial',
  needs_authorization: 'Needs auth',
  needs_referral: 'Needs referral',
  not_covered: 'Not covered',
};

/* ------------------------------------------------------------------------------------
 * Escalation — §17: open > acknowledged > resolved
 * ---------------------------------------------------------------------------------- */

export const ESCALATION_STATUSES = ['open', 'acknowledged', 'resolved'] as const;
export type EscalationStatus = (typeof ESCALATION_STATUSES)[number];

export const ESCALATION_STATUS_LABELS: Readonly<Record<EscalationStatus, string>> = {
  open: 'Open',
  acknowledged: 'Acknowledged',
  resolved: 'Resolved',
};

/** §11.1 trigger dimension. */
export const ESCALATION_TRIGGERS = [
  'triage_high',
  'triage_urgent_emergency',
  'clinical_question',
  'caller_requested_human',
  'agent_initiated',
] as const;
export type EscalationTrigger = (typeof ESCALATION_TRIGGERS)[number];

export const ESCALATION_TRIGGER_LABELS: Readonly<Record<EscalationTrigger, string>> = {
  triage_high: 'Triage High',
  triage_urgent_emergency: 'Urgent or Emergency',
  clinical_question: 'Clinical question',
  caller_requested_human: 'Caller requested human',
  agent_initiated: 'Agent-initiated',
};

/**
 * §11.2 default acknowledgement thresholds: "30 minutes for Urgent, 4 hours otherwise".
 * These feed the §4.6 Overview attention banner.
 */
export const ESCALATION_ACK_THRESHOLD_MINUTES = {
  urgent: 30,
  default: 240,
} as const;

/* ------------------------------------------------------------------------------------
 * Review request — §17:
 *   eligible > called > reached > asked > agreed > link_sent > posted | declined | opt_out
 * ---------------------------------------------------------------------------------- */

export const REVIEW_REQUEST_STATUSES = [
  'eligible',
  'called',
  'reached',
  'asked',
  'agreed',
  'link_sent',
  'posted',
  'declined',
  'opt_out',
] as const;
export type ReviewRequestStatus = (typeof REVIEW_REQUEST_STATUSES)[number];

export const REVIEW_REQUEST_STATUS_LABELS: Readonly<Record<ReviewRequestStatus, string>> = {
  eligible: 'Eligible',
  called: 'Called',
  reached: 'Reached',
  asked: 'Asked',
  agreed: 'Agreed',
  link_sent: 'Link sent',
  posted: 'Posted',
  declined: 'Declined',
  opt_out: 'Opt-out',
};

/* ------------------------------------------------------------------------------------
 * Campaign contact — §17:
 *   queued > attempted > reached > booked | exhausted | opt_out
 * ---------------------------------------------------------------------------------- */

export const CAMPAIGN_CONTACT_STATUSES = [
  'queued',
  'attempted',
  'reached',
  'booked',
  'exhausted',
  'opt_out',
] as const;
export type CampaignContactStatus = (typeof CAMPAIGN_CONTACT_STATUSES)[number];

export const CAMPAIGN_CONTACT_STATUS_LABELS: Readonly<Record<CampaignContactStatus, string>> = {
  queued: 'Queued',
  attempted: 'Attempted',
  reached: 'Reached',
  booked: 'Booked',
  exhausted: 'Exhausted',
  opt_out: 'Opt-out',
};

/** §14.2 campaign-level status (distinct from campaign-contact status above). */
export const CAMPAIGN_STATUSES = ['draft', 'scheduled', 'running', 'paused', 'completed'] as const;
export type CampaignStatus = (typeof CAMPAIGN_STATUSES)[number];

export const CAMPAIGN_STATUS_LABELS: Readonly<Record<CampaignStatus, string>> = {
  draft: 'Draft',
  scheduled: 'Scheduled',
  running: 'Running',
  paused: 'Paused',
  completed: 'Completed',
};

/* ------------------------------------------------------------------------------------
 * Flag — §17: submitted > under_review > resolved
 * ---------------------------------------------------------------------------------- */

export const FLAG_STATUSES = ['submitted', 'under_review', 'resolved'] as const;
export type FlagStatus = (typeof FLAG_STATUSES)[number];

export const FLAG_STATUS_LABELS: Readonly<Record<FlagStatus, string>> = {
  submitted: 'Submitted',
  under_review: 'Under review',
  resolved: 'Resolved',
};

/* ------------------------------------------------------------------------------------
 * Optimization event — §17: detected > in_tuning > deployed > verified
 * ---------------------------------------------------------------------------------- */

export const OPTIMIZATION_EVENT_STATUSES = ['detected', 'in_tuning', 'deployed', 'verified'] as const;
export type OptimizationEventStatus = (typeof OPTIMIZATION_EVENT_STATUSES)[number];

export const OPTIMIZATION_EVENT_STATUS_LABELS: Readonly<Record<OptimizationEventStatus, string>> = {
  detected: 'Detected',
  in_tuning: 'In tuning',
  deployed: 'Deployed',
  verified: 'Verified',
};

/**
 * §12.1 loop stage mapping. See BUILD_NOTES.md § B10 — the loop's stage names are not
 * the enum's names, and the mapping is an interpretation, so it lives here once.
 */
export const OPTIMIZATION_FLAGGED_STATUSES = ['detected', 'in_tuning'] as const;
export const OPTIMIZATION_APPLIED_STATUSES = ['deployed', 'verified'] as const;

/* ------------------------------------------------------------------------------------
 * Call disposition — §17 / §10.1
 * ---------------------------------------------------------------------------------- */

export const CALL_DISPOSITIONS = [
  'in_progress',
  'booked',
  'info_only',
  'verified',
  'confirmed',
  'review_requested',
  'reengaged_booked',
  'escalated',
  'voicemail',
  'no_answer',
  'abandoned',
] as const;
export type CallDisposition = (typeof CALL_DISPOSITIONS)[number];

export const CALL_DISPOSITION_LABELS: Readonly<Record<CallDisposition, string>> = {
  in_progress: 'In progress',
  booked: 'Booked',
  info_only: 'Info only',
  verified: 'Verified',
  confirmed: 'Confirmed',
  review_requested: 'Review requested',
  reengaged_booked: 'Reengaged-booked',
  escalated: 'Escalated',
  voicemail: 'Voicemail',
  no_answer: 'No answer',
  abandoned: 'Abandoned',
};

/* ------------------------------------------------------------------------------------
 * Supporting dimensions used across tabs (each traceable to a spec line)
 * ---------------------------------------------------------------------------------- */

/** §5.2 / §6.2: "Triage flag (None, Low, High, Urgent; red accents on High and Urgent)". */
export const TRIAGE_FLAGS = ['none', 'low', 'high', 'urgent'] as const;
export type TriageFlag = (typeof TRIAGE_FLAGS)[number];

export const TRIAGE_FLAG_LABELS: Readonly<Record<TriageFlag, string>> = {
  none: 'None',
  low: 'Low',
  high: 'High',
  urgent: 'Urgent',
};

/** §5.2 "Source (Voice, WhatsApp, Web Chat, Form)". */
export const APPOINTMENT_SOURCES = ['voice', 'whatsapp', 'web_chat', 'form'] as const;
export type AppointmentSource = (typeof APPOINTMENT_SOURCES)[number];

export const APPOINTMENT_SOURCE_LABELS: Readonly<Record<AppointmentSource, string>> = {
  voice: 'Voice',
  whatsapp: 'WhatsApp',
  web_chat: 'Web Chat',
  form: 'Form',
};

/** §4.1 bookings-over-time chart is "stacked by source (Voice, WhatsApp, Web Chat)" — no Form. */
export const BOOKING_CHART_SOURCES = ['voice', 'whatsapp', 'web_chat'] as const satisfies readonly AppointmentSource[];

/** §9.1 "split by channel: WhatsApp vs Web Chat". */
export const CHAT_CHANNELS = ['whatsapp', 'web_chat'] as const;
export type ChatChannel = (typeof CHAT_CHANNELS)[number];

/** §10.1 "direction (inbound, outbound)". */
export const CALL_DIRECTIONS = ['inbound', 'outbound'] as const;
export type CallDirection = (typeof CALL_DIRECTIONS)[number];

/**
 * §10.1 agent dimension: "agent (Receptionist, VOB, Verifier, Review Taker, Reengagement)".
 * `verifier` is a real, distinct agent — see BUILD_NOTES.md § B2. It has no nav tab of its
 * own, because §3 does not list one.
 */
export const AGENT_IDS = [
  'receptionist',
  'vob',
  'verifier',
  'chat',
  'review_taker',
  'reengagement',
] as const;
export type AgentId = (typeof AGENT_IDS)[number];

/**
 * §2.6: "Custom enterprise agents therefore get a dashboard page with zero frontend work."
 *
 * That claim was quietly false: `CallInteraction.agent` was typed as `AgentId`, a closed
 * union of the six standard agents, so **no interaction could ever be attributed to a
 * custom agent** and its analytics page rendered nothing but em-dashes. The registry could
 * describe a custom agent; the interaction model could not reference one.
 *
 * Custom agents are declared here because fixtures are typed data. In a real deployment the
 * set is open and comes from the registry — the *frontend* still needs zero work, which is
 * what §2.6 actually claims. Adding an agent here is fixture authoring, not frontend work.
 */
export const CUSTOM_AGENT_IDS = ['post_op_followup'] as const;
export type CustomAgentId = (typeof CUSTOM_AGENT_IDS)[number];

/** Any agent that can be attributed an interaction: the six standard, plus custom agents. */
export type InteractionAgentId = AgentId | CustomAgentId;

export const AGENT_LABELS: Readonly<Record<InteractionAgentId, string>> = {
  receptionist: 'Receptionist',
  vob: 'VOB Agent',
  verifier: 'Verifier',
  chat: 'Chat Agents',
  review_taker: 'Review Taker',
  reengagement: 'Reengagement',
  post_op_followup: 'Post-Op Follow-Up',
};

/** §5.4 "each Verifier attempt with outcome". */
export const CONFIRMATION_ATTEMPT_OUTCOMES = [
  'reached',
  'voicemail',
  'no_answer',
  'confirmed',
  'reschedule_requested',
] as const;
export type ConfirmationAttemptOutcome = (typeof CONFIRMATION_ATTEMPT_OUTCOMES)[number];

export const CONFIRMATION_ATTEMPT_OUTCOME_LABELS: Readonly<Record<ConfirmationAttemptOutcome, string>> = {
  reached: 'Reached',
  voicemail: 'Voicemail',
  no_answer: 'No answer',
  confirmed: 'Confirmed',
  reschedule_requested: 'Reschedule requested',
};

/** §8.3 "Mark resolved (with reason picker: ...)". */
export const VOB_RESOLVE_REASONS = [
  'verified_manually',
  'patient_rescheduled',
  'patient_cancelled',
  'other',
] as const;
export type VobResolveReason = (typeof VOB_RESOLVE_REASONS)[number];

export const VOB_RESOLVE_REASON_LABELS: Readonly<Record<VobResolveReason, string>> = {
  verified_manually: 'Verified manually',
  patient_rescheduled: 'Patient rescheduled',
  patient_cancelled: 'Patient cancelled',
  other: 'Other',
};

/** §12.3 "the five grading dimensions". Order is the spec's order. */
export const GRADING_DIMENSIONS = [
  'accuracy',
  'compliance',
  'conversation_quality',
  'task_completion',
  'efficiency',
] as const;
export type GradingDimension = (typeof GRADING_DIMENSIONS)[number];

export const GRADING_DIMENSION_LABELS: Readonly<Record<GradingDimension, string>> = {
  accuracy: 'Accuracy',
  compliance: 'Compliance',
  conversation_quality: 'Conversation quality',
  task_completion: 'Task completion',
  efficiency: 'Efficiency',
};

export const GRADING_DIMENSION_DESCRIPTIONS: Readonly<Record<GradingDimension, string>> = {
  accuracy: 'Information given matched the knowledge base',
  compliance: 'Required disclosures made, clinical boundary respected, consent language delivered where applicable',
  conversation_quality: 'Tone, interruptions handling, proper opening and closing',
  task_completion: 'Did the call achieve its objective (booking, verification, confirmation, review ask)',
  efficiency: 'Handle time vs benchmark for the call type',
};

/** §8.1 aging SLA: "amber past 24 hours in a non-terminal state, red past 48 hours". */
export const VOB_AGING_THRESHOLD_HOURS = {
  amber: 24,
  red: 48,
} as const;

/** §2.1 data modes. */
export const DATA_MODES = ['NON_PHI', 'PHI_BAA'] as const;
export type DataMode = (typeof DATA_MODES)[number];

export const DATA_MODE_LABELS: Readonly<Record<DataMode, string>> = {
  NON_PHI: 'NON-PHI',
  PHI_BAA: 'PHI-BAA',
};

/** §2.2 roles. "Owner/Admin" is one role — see BUILD_NOTES.md § B7. */
export const ROLES = ['OWNER_ADMIN', 'MANAGER', 'VIEWER'] as const;
export type Role = (typeof ROLES)[number];

export const ROLE_LABELS: Readonly<Record<Role, string>> = {
  OWNER_ADMIN: 'Owner/Admin',
  MANAGER: 'Manager',
  VIEWER: 'Viewer',
};

/** §2.8 "per-location setting for one-party vs two-party consent states". */
export const RECORDING_CONSENT_MODES = ['one_party', 'two_party'] as const;
export type RecordingConsentMode = (typeof RECORDING_CONSENT_MODES)[number];

/** §16.5 "source of suppression: patient opt-out, manual add, complaint". */
export const SUPPRESSION_SOURCES = ['patient_opt_out', 'manual_add', 'complaint'] as const;
export type SuppressionSource = (typeof SUPPRESSION_SOURCES)[number];

export const SUPPRESSION_SOURCE_LABELS: Readonly<Record<SuppressionSource, string>> = {
  patient_opt_out: 'Patient opt-out',
  manual_add: 'Manual add',
  complaint: 'Complaint',
};

/** §15.2 "Status tracking per request: requested, in review, scheduled, live". */
export const KNOWLEDGE_REQUEST_STATUSES = ['requested', 'in_review', 'scheduled', 'live'] as const;
export type KnowledgeRequestStatus = (typeof KNOWLEDGE_REQUEST_STATUSES)[number];

export const KNOWLEDGE_REQUEST_STATUS_LABELS: Readonly<Record<KnowledgeRequestStatus, string>> = {
  requested: 'Requested',
  in_review: 'In review',
  scheduled: 'Scheduled',
  live: 'Live',
};

/** §2.7 "Language of patient interactions is a data dimension". §6.2 "(en, es, other)". */
export const LANGUAGES = ['en', 'es', 'other'] as const;
export type Language = (typeof LANGUAGES)[number];

export const LANGUAGE_LABELS: Readonly<Record<Language, string>> = {
  en: 'English',
  es: 'Spanish',
  other: 'Other',
};
