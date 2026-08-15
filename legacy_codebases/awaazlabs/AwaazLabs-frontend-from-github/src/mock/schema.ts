/**
 * MOCK DATA SCHEMA — spec §2.5 (patient data envelope), §2.4 (multi-location),
 * §2.6 (agent registry).
 *
 * FROZEN FILE (Foundation).
 *
 * §2.5 is a data-minimization contract, not a suggestion: "No DOB display, no SSN, no
 * clinical notes, no diagnosis." The guide's Part F.4 sharpens it: the schema "must make
 * it structurally impossible to add DOB, SSN, clinical notes, or diagnosis fields — don't
 * just omit them by convention, don't define the fields at all."
 *
 * `NoPhi<T>` below enforces that at the type level. Adding a forbidden key to any type
 * wrapped in it does not merely lint — it makes the type unassignable, and every fixture
 * and consumer fails to compile.
 */

import type {
  AgentId,
  InteractionAgentId,
  AppointmentSource,
  AppointmentStatus,
  CallDirection,
  CallDisposition,
  CampaignContactStatus,
  CampaignStatus,
  ConfirmationAttemptOutcome,
  EscalationStatus,
  EscalationTrigger,
  FlagStatus,
  GradingDimension,
  KnowledgeRequestStatus,
  Language,
  OptimizationEventStatus,
  RecordingConsentMode,
  ReviewRequestStatus,
  Role,
  SuppressionSource,
  TriageFlag,
  VobResolveReason,
  VobStatus,
} from '@/shared/status-models';

/* ==================================================================================
 * The PHI barrier
 * ================================================================================== */

/**
 * Field names that must never exist on any patient-bearing type. Spelling variants are
 * included deliberately: the barrier is only as good as the names it knows.
 */
type ForbiddenPhiKey =
  | 'dob'
  | 'dateOfBirth'
  | 'birthDate'
  | 'birthdate'
  | 'ssn'
  | 'socialSecurityNumber'
  | 'diagnosis'
  | 'diagnoses'
  | 'icd10'
  | 'icdCode'
  | 'clinicalNote'
  | 'clinicalNotes'
  | 'medicalHistory'
  | 'medications'
  | 'allergies'
  | 'labResults';

/**
 * Compile-time barrier. If `T` declares any forbidden key, `NoPhi<T>` resolves to a
 * poison type that nothing can satisfy, so the fixture files stop compiling.
 *
 * Try it: add `dob: string` to `PatientContact` and run `npm run typecheck`.
 */
type NoPhi<T> = Extract<keyof T, ForbiddenPhiKey> extends never
  ? T
  : { readonly __PHI_VIOLATION__: 'This type declares a field forbidden by spec §2.5' };

/* ==================================================================================
 * Patient envelope (§2.5)
 * ================================================================================== */

/**
 * The identity block. Returned as a whole or not at all — never partially redacted.
 *
 * This is the unit of gating (guide Rule 6). A Viewer, or any role in NON-PHI mode,
 * receives `identity: null`. The phone number is not "hidden by CSS"; it is absent from
 * the object. There is nothing on the client to reveal.
 */
export type PatientIdentity = NoPhi<{
  readonly firstName: string;
  readonly lastName: string;
  /**
   * E.164. §5.2: "masked as pattern, click-to-reveal, reveal audited". Masking is a
   * presentation concern (`MaskedValue`); the raw value only ever reaches a client that
   * the data-access layer decided may see it.
   */
  readonly phoneE164: string;
}>;

/** §2.5 "insurance carrier and member context captured for VOB". */
export type InsuranceContext = NoPhi<{
  readonly carrier: string;
  readonly plan: string;
  readonly memberIdMasked: string;
  readonly groupNumber: string | null;
}>;

/**
 * The contact record. Every patient-level row in the app carries one of these.
 *
 * Note what is NOT here, and cannot be: date of birth, SSN, diagnosis, clinical notes.
 * "The EHR remains the system of record for the patient; this dashboard is the system of
 * record for interactions and outcomes." (§2.5)
 */
export type PatientContact = NoPhi<{
  readonly id: string;
  readonly identity: PatientIdentity | null;
  readonly insurance: InsuranceContext | null;
  /** §2.5 "treatment/service interest" */
  readonly serviceInterest: string;
  readonly language: Language;
  readonly locationId: string;
  readonly consentBasis: string | null;
  readonly suppressed: boolean;
}>;

/* ==================================================================================
 * Organization & location (§2.4, §16.5)
 * ================================================================================== */

export interface BusinessHours {
  /** 0 = Sunday. Absent day = closed. */
  readonly day: number;
  readonly openMinute: number;
  readonly closeMinute: number;
}

export interface MockLocation {
  readonly id: string;
  readonly name: string;
  /** IANA zone. §2.7: "All timestamps stored UTC, rendered in the location's configured timezone." */
  readonly timezone: string;
  readonly businessHours: readonly BusinessHours[];
  readonly holidays: readonly string[];
  readonly recordingConsentMode: RecordingConsentMode;
  readonly escalationForwardingNumber: string;
}

export interface MockOrganization {
  readonly id: string;
  readonly name: string;
  readonly locations: readonly MockLocation[];
  /**
   * §4.3 / §16.5: "average appointment value configuration (feeds revenue cards)".
   * `null` means unset, which per §4.3 hides the revenue card entirely.
   */
  readonly avgAppointmentValueUsd: number | null;
  /**
   * §4.1: the no-show card "hides if outcome data unavailable for this clinic, never
   * render misleading zeros". See BUILD_NOTES.md § B9.
   */
  readonly outcomeDataAvailable: boolean;
  /** §16.4 */
  readonly planMinutes: number;
  readonly planChatSessions: number;
}

/** §2.4: "Single-location clinics see no filter." */
export function isMultiLocation(org: MockOrganization): boolean {
  return org.locations.length > 1;
}

/* ==================================================================================
 * Agent registry (§2.6)
 * ================================================================================== */

export const AGENT_CHANNELS = ['voice', 'chat'] as const;
export type AgentChannel = (typeof AGENT_CHANNELS)[number];

export const AGENT_TYPES = ['inbound', 'outbound'] as const;
export type AgentType = (typeof AGENT_TYPES)[number];

/** §2.6 "a metrics contract (list of KPI definitions it emits)". */
export interface KpiDefinition {
  readonly key: string;
  readonly label: string;
  readonly format: 'count' | 'percent' | 'duration_ms' | 'duration_s' | 'currency_usd';
  /** Rendered in the card's info tooltip where the spec calls for one. */
  readonly description?: string;
}

/**
 * §2.6: "Every agent, standard or custom, renders from the same schema... Custom
 * enterprise agents therefore get a dashboard page with zero frontend work."
 *
 * `icon` is a lucide-react icon name, resolved through a single allow-list map. It is not
 * a component reference and not an arbitrary string: an unbounded icon name from a
 * registry entry would be a rendering injection point.
 */
export interface AgentRegistryEntry {
  readonly id: AgentId | string;
  readonly name: string;
  readonly type: AgentType;
  readonly channel: AgentChannel;
  readonly icon: string;
  readonly metricsContract: readonly KpiDefinition[];
  /** Standard agents have bespoke tabs; custom agents render via /agents/[slug]. */
  readonly isCustom: boolean;
  readonly slug: string;
}

/* ==================================================================================
 * Operational records
 * ================================================================================== */

export interface AppointmentTimelineEvent {
  readonly at: string;
  readonly label: string;
  readonly actor: string;
}

/** §5.4 "Confirmation and reminder history: each Verifier attempt with outcome". */
export interface ConfirmationAttempt {
  readonly at: string;
  readonly outcome: ConfirmationAttemptOutcome;
}

export type Appointment = NoPhi<{
  readonly id: string;
  readonly contactId: string;
  /** ISO-8601 UTC. Rendered in the location's timezone. */
  readonly startsAtUtc: string;
  readonly serviceInterest: string;
  readonly source: AppointmentSource;
  readonly language: Language;
  readonly insuranceCaptured: boolean;
  readonly vobId: string | null;
  readonly triage: TriageFlag;
  readonly status: AppointmentStatus;
  readonly bookedByAgent: AgentId;
  readonly bookedAtUtc: string;
  readonly locationId: string;
  /** §4.5 / §6.1: bookings outside configured business hours. Precomputed on the fixture. */
  readonly afterHours: boolean;
  readonly originatingInteractionId: string | null;
  readonly timeline: readonly AppointmentTimelineEvent[];
  readonly confirmationAttempts: readonly ConfirmationAttempt[];
  readonly staffNotes: readonly { readonly at: string; readonly author: string; readonly body: string }[];
}>;

/** §8.2 "captured benefits (copay, deductible, out-of-pocket, coverage notes)". */
export interface CapturedBenefits {
  readonly copayUsd: number | null;
  readonly deductibleUsd: number | null;
  readonly outOfPocketMaxUsd: number | null;
  readonly coverageNotes: string | null;
}

/** §8.2 "per-attempt call log with recordings and transcripts". */
export interface VobAttempt {
  readonly at: string;
  readonly durationSeconds: number;
  readonly outcome: string;
  readonly interactionId: string | null;
  readonly payerReferenceNumber: string | null;
}

export type VobRecord = NoPhi<{
  readonly id: string;
  readonly contactId: string;
  readonly payer: string;
  readonly plan: string;
  readonly status: VobStatus;
  readonly appointmentId: string | null;
  readonly assignedTo: string | null;
  readonly requestedAtUtc: string;
  readonly lastAttemptAtUtc: string | null;
  readonly attempts: readonly VobAttempt[];
  readonly benefits: CapturedBenefits;
  readonly priorAuthRequired: boolean;
  readonly referralRequired: boolean;
  readonly ivrNavigationSucceeded: boolean;
  readonly payerRepReached: boolean;
  readonly locationId: string;
  readonly resolvedReason: VobResolveReason | null;
  /** Persisted staff notes from the backend (live VOB queue). */
  readonly staffNotes?: readonly { readonly at: string; readonly author: string; readonly body: string }[];
  /** True when staff marked the row resolved in the dashboard. */
  readonly resolved?: boolean;
  readonly statusTimeline: readonly { readonly at: string; readonly status: VobStatus; readonly actor: string }[];
}>;

/** §12.3 per-call sub-scores rolling into the overall grade. */
export type GradeBreakdown = Readonly<Record<GradingDimension, number>>;

export interface QaGrade {
  readonly overall: number;
  readonly breakdown: GradeBreakdown;
}

export interface TranscriptTurn {
  readonly speaker: 'agent' | 'patient';
  readonly at: string;
  readonly text: string;
  /** §10.1 "PII redaction markers" — character ranges within `text` that were redacted. */
  readonly redactions: readonly { readonly start: number; readonly end: number; readonly kind: string }[];
}

/**
 * §10.1 drawer contents that are role-gated: "Audio player for the recording (role-gated,
 * playback audited)", "Full transcript". Bundled into one nullable block so that a Viewer
 * receives `media: null` and there is literally nothing to play or read.
 */
export interface InteractionMedia {
  readonly recordingUrl: string;
  readonly transcript: readonly TranscriptTurn[];
  /** §10.1 "Recording-consent disclosure event shown when two-party consent mode was active". */
  readonly consentDisclosureAtUtc: string | null;
}

export type CallInteraction = NoPhi<{
  readonly id: string;
  readonly kind: 'call';
  readonly atUtc: string;
  readonly direction: CallDirection;
  /**
   * §2.6: a custom agent must be attributable an interaction, or its analytics page has
   * nothing to render and the 'zero frontend work' claim is empty. `AgentId` alone (the six
   * standard agents) made that structurally impossible.
   */
  readonly agent: InteractionAgentId;
  readonly contactId: string | null;
  readonly durationSeconds: number;
  readonly disposition: CallDisposition;
  readonly triage: TriageFlag;
  readonly grade: QaGrade | null;
  readonly locationId: string;
  readonly media: InteractionMedia | null;
  readonly firstAudioResponseMs: number;
  readonly costUsd: number;
  readonly linked: {
    readonly appointmentId: string | null;
    readonly vobId: string | null;
    readonly reviewRequestId: string | null;
    readonly campaignId: string | null;
  };
}>;

export const CHAT_SESSION_OUTCOMES = ['contained', 'resolved', 'escalated', 'booked'] as const;
export type ChatSessionOutcome = (typeof CHAT_SESSION_OUTCOMES)[number];

export interface ChatMessage {
  readonly at: string;
  readonly speaker: 'agent' | 'patient' | 'human_staff';
  readonly text: string;
  /** §10.2 "handoff markers where a human took over". */
  readonly isHandoffMarker: boolean;
}

export type ChatInteraction = NoPhi<{
  readonly id: string;
  readonly kind: 'chat';
  readonly atUtc: string;
  readonly channel: 'whatsapp' | 'web_chat';
  readonly contactId: string | null;
  readonly lastMessageAtUtc: string;
  readonly outcome: ChatSessionOutcome;
  readonly messageCount: number;
  readonly intent: string;
  readonly language: Language;
  readonly locationId: string;
  readonly responseLatencyMs: number;
  readonly grade: QaGrade | null;
  readonly linked: { readonly appointmentId: string | null };
  /** Null for Viewer / NON-PHI, exactly as with calls. */
  readonly messages: readonly ChatMessage[] | null;
}>;

export type Escalation = NoPhi<{
  readonly id: string;
  readonly atUtc: string;
  readonly contactId: string;
  readonly sourceInteractionId: string;
  readonly trigger: EscalationTrigger;
  readonly routedTo: string;
  readonly status: EscalationStatus;
  readonly acknowledgedAtUtc: string | null;
  readonly acknowledgedBy: string | null;
  readonly resolutionNote: string | null;
  readonly locationId: string;
}>;

/* ==================================================================================
 * Quality (§12)
 * ================================================================================== */

export interface OptimizationEvent {
  readonly id: string;
  readonly detectedAtUtc: string;
  readonly agent: AgentId;
  readonly status: OptimizationEventStatus;
  /** §12.4 client-safe language, controlled vocabulary. Never internal tuning mechanics. */
  readonly whatWasDetected: string;
  readonly whatWasChanged: string;
  /** Measured after deployment. Null until a `verified` event has a delta. */
  readonly gradeDelta: number | null;
  readonly deployedAtUtc: string | null;
  readonly verifiedAtUtc: string | null;
}

export interface FlaggedInteraction {
  readonly id: string;
  readonly interactionId: string;
  readonly submittedAtUtc: string;
  readonly submittedBy: string;
  readonly status: FlagStatus;
  readonly reason: string;
  readonly resolutionNote: string | null;
}

/* ==================================================================================
 * Growth (§13, §14)
 * ================================================================================== */

export type ReviewRequest = NoPhi<{
  readonly id: string;
  readonly contactId: string;
  readonly appointmentId: string;
  readonly status: ReviewRequestStatus;
  readonly calledAtUtc: string | null;
  readonly callDurationSeconds: number | null;
  readonly linkClicked: boolean;
  readonly postedRating: number | null;
  readonly postedAtUtc: string | null;
  readonly locationId: string;
  readonly interactionId: string | null;
}>;

/** §13.1 / §13.2 "private feedback capture after the ask". */
export type PrivateFeedback = NoPhi<{
  readonly id: string;
  readonly atUtc: string;
  readonly contactId: string;
  readonly summary: string;
  readonly sourceInteractionId: string;
  readonly status: 'new' | 'actioned';
  readonly locationId: string;
}>;

export type PublishedReview = NoPhi<{
  readonly id: string;
  readonly atUtc: string;
  readonly rating: number;
  readonly excerpt: string;
  readonly url: string;
  readonly attributed: boolean;
  readonly locationId: string;
}>;

export const CAMPAIGN_TYPES = ['reengagement', 'no_show_recovery', 'recall'] as const;
export type CampaignType = (typeof CAMPAIGN_TYPES)[number];

export type CampaignContact = NoPhi<{
  readonly id: string;
  readonly contactId: string;
  readonly status: CampaignContactStatus;
  readonly attempts: number;
  readonly lastOutcome: string | null;
  readonly bookedAppointmentId: string | null;
  readonly optOut: boolean;
}>;

export interface Campaign {
  readonly id: string;
  readonly name: string;
  readonly type: CampaignType;
  readonly status: CampaignStatus;
  readonly audienceSize: number;
  readonly startedAtUtc: string | null;
  readonly locationId: string;
  /** §14.2 "Audience definition summary (segment rules...)" */
  readonly audienceDefinition: readonly string[];
  /** §14.2 pacing settings, displayed read-only. */
  readonly pacing: {
    readonly callingWindowLocal: string;
    readonly maxAttempts: number;
    readonly retrySpacingHours: number;
  };
  readonly contacts: readonly CampaignContact[];
}

/* ==================================================================================
 * Knowledge (§15) & Settings (§16)
 * ================================================================================== */

/** §15.1 the eight documented categories. */
export const KNOWLEDGE_CATEGORIES = [
  'services_and_treatments',
  'pricing',
  'providers_and_schedules',
  'hours_and_holidays',
  'insurance_carriers_accepted',
  'faq',
  'booking_rules',
  'escalation_routing',
] as const;
export type KnowledgeCategory = (typeof KNOWLEDGE_CATEGORIES)[number];

export interface KnowledgeBlock {
  readonly category: KnowledgeCategory;
  readonly locationId: string | null;
  readonly entries: readonly { readonly label: string; readonly value: string }[];
}

export interface KnowledgeChangeRequest {
  readonly id: string;
  readonly category: KnowledgeCategory;
  readonly proposedChange: string;
  readonly reason: string;
  readonly requestedBy: string;
  readonly requestedAtUtc: string;
  readonly status: KnowledgeRequestStatus;
  readonly history: readonly { readonly at: string; readonly status: KnowledgeRequestStatus }[];
}

export interface Member {
  readonly id: string;
  readonly email: string;
  readonly name: string;
  readonly role: Role;
  readonly lastActiveUtc: string;
  readonly mfaEnabled: boolean;
}

export interface PhoneLine {
  readonly id: string;
  readonly number: string;
  readonly kind: 'voice' | 'whatsapp';
  readonly locationId: string;
  readonly healthy: boolean;
  readonly lastCheckedUtc: string;
}

export type SuppressionEntry = NoPhi<{
  readonly id: string;
  readonly phoneE164: string;
  readonly source: SuppressionSource;
  readonly addedAtUtc: string;
  readonly consentBasis: string | null;
}>;

export interface Invoice {
  readonly id: string;
  readonly periodLabel: string;
  readonly amountUsd: number;
  readonly status: 'paid' | 'due';
  readonly downloadUrl: string;
}

/* ==================================================================================
 * The complete fixture bundle for one organization
 * ================================================================================== */

export interface OrgFixture {
  readonly org: MockOrganization;
  readonly contacts: readonly PatientContact[];
  readonly appointments: readonly Appointment[];
  readonly vobRecords: readonly VobRecord[];
  readonly calls: readonly CallInteraction[];
  readonly chats: readonly ChatInteraction[];
  readonly escalations: readonly Escalation[];
  readonly optimizationEvents: readonly OptimizationEvent[];
  readonly flags: readonly FlaggedInteraction[];
  readonly reviewRequests: readonly ReviewRequest[];
  readonly privateFeedback: readonly PrivateFeedback[];
  readonly publishedReviews: readonly PublishedReview[];
  readonly campaigns: readonly Campaign[];
  readonly knowledgeBlocks: readonly KnowledgeBlock[];
  readonly knowledgeRequests: readonly KnowledgeChangeRequest[];
  readonly members: readonly Member[];
  readonly lines: readonly PhoneLine[];
  readonly suppressionList: readonly SuppressionEntry[];
  readonly invoices: readonly Invoice[];
  readonly agents: readonly AgentRegistryEntry[];
  /** §4.5 "Live calls now, with refresh timestamp". */
  readonly liveCallsNow: number;
  /** §16.4 current-cycle consumption. */
  readonly minutesConsumed: number;
  readonly chatSessionsConsumed: number;
}
