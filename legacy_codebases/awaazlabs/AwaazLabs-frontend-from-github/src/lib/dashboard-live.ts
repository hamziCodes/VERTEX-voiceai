import type { AppointmentStats, VobCounts } from '@/lib/metrics';
import type { AppointmentView, CallInteractionView, ChatInteractionView, GatedRows, Session, VobRecordView } from '@/mock/data-access';
import { canAccessMedia } from '@/mock/data-access';
import type { Escalation } from '@/mock/schema';
import {
  AGENT_IDS,
  APPOINTMENT_SOURCES,
  APPOINTMENT_STATUSES,
  CALL_DISPOSITIONS,
  CONFIRMATION_ATTEMPT_OUTCOMES,
  ESCALATION_STATUSES,
  ESCALATION_TRIGGERS,
  LANGUAGES,
  TRIAGE_FLAGS,
  VOB_RESOLVE_REASONS,
  VOB_STATUSES,
} from '@/shared/status-models';
import { hasRecordingSource, recordingProxyUrl } from '@/lib/recording-proxy';
import type {
  AgentId,
  AppointmentSource,
  AppointmentStatus,
  CallDisposition,
  ConfirmationAttemptOutcome,
  EscalationStatus,
  EscalationTrigger,
  Language,
  TriageFlag,
  VobStatus,
  VobResolveReason,
} from '@/shared/status-models';

export interface DashboardStatsDto {
  readonly bookedToday: number;
  readonly bookedSameWeekdayLastWeek: number;
  readonly bookedThisWeek: number;
  readonly bookingRateThisWeek: number | null;
  readonly upcomingNext7Days: number;
  readonly noShowsAndCancellationsThisWeek: number;
  readonly noShowCancelRateThisWeek: number | null;
  readonly confirmationRate: number | null;
  readonly noShowRate30d: number | null;
  readonly nextAppointment?: { readonly patientName: string; readonly startsAt: string } | null;
}

interface PatientSummaryDto {
  readonly firstName: string | null;
  readonly lastName: string | null;
  readonly fullName?: string | null;
  readonly phoneMasked: string | null;
  readonly phoneE164: null;
}

interface ConfirmationAttemptDto {
  readonly at: string;
  readonly outcome: string;
  readonly channel: string;
}

interface TimelineEventDto {
  readonly at: string;
  readonly label: string;
  readonly actor: string;
}

interface AppointmentRowDto {
  readonly id: string;
  readonly locationId: string;
  readonly locationName?: string | null;
  readonly patientId: string;
  readonly bookingId: string | null;
  readonly callId: string | null;
  readonly vobId: string | null;
  readonly status: string;
  readonly source: string;
  readonly serviceInterest: string;
  readonly language: string;
  readonly triage: string;
  readonly insuranceCaptured: boolean;
  readonly bookedByAgent: string;
  readonly bookedAt: string;
  readonly afterHours: boolean;
  readonly startsAt: string | null;
  readonly appointmentTextRaw: string | null;
  readonly needsReview: boolean;
  readonly reviewReasons: readonly string[];
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly patient: PatientSummaryDto;
  readonly vobStatus: string | null;
  readonly confirmationAttempts: readonly ConfirmationAttemptDto[];
  readonly timeline: readonly TimelineEventDto[];
  readonly staffNotes: readonly { readonly at: string; readonly author: string; readonly body: string }[];
  readonly bookingRef: { readonly callId: string | null; readonly transcriptAvailable: boolean } | null;
}

interface EscalationRowDto {
  readonly id: string;
  readonly locationId: string;
  readonly bookingId: string | null;
  readonly callId: string | null;
  readonly patientId: string | null;
  readonly trigger: string;
  readonly routedTo: string | null;
  readonly status: string;
  readonly acknowledgedAt: string | null;
  readonly acknowledgedBy: string | null;
  readonly resolutionNote: string | null;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly patient: { readonly firstName: string | null; readonly lastName: string | null } | null;
  readonly locationName: string | null;
}

export interface EscalationStatsDto {
  readonly total: number;
  readonly thisWeek: number;
  readonly ackRate: number | null;
  readonly medianTimeToAckSeconds: number | null;
  readonly triggerCounts: Record<string, number>;
}

export interface LiveAppointmentsSnapshot {
  readonly gated: GatedRows<AppointmentView>;
  readonly stats: DashboardStatsDto;
  readonly vobStatusById: ReadonlyMap<string, VobStatus>;
}

export interface LiveEscalationsSnapshot {
  readonly gated: GatedRows<LiveEscalation>;
  readonly stats: EscalationStatsDto;
}

interface CallTranscriptTurnDto {
  readonly speaker: 'agent' | 'patient';
  readonly at: string;
  readonly text: string;
}

interface CallRowDto {
  readonly id: string;
  readonly callId: string;
  readonly at: string;
  readonly direction: 'inbound' | 'outbound';
  readonly agent: 'receptionist' | 'vob';
  readonly patient: PatientSummaryDto;
  readonly durationSeconds: number;
  readonly disposition: string;
  readonly triage: string;
  readonly locationId: string | null;
  readonly locationName: string | null;
  readonly callbackNumberMasked: string | null;
  readonly recordingUrl: string | null;
  readonly transcript: readonly CallTranscriptTurnDto[] | null;
  readonly summary: string | null;
}

export interface LiveCallsSnapshot {
  readonly gated: GatedRows<CallInteractionView>;
}

interface ChatMessageDto {
  readonly at: string;
  readonly speaker: 'agent' | 'patient' | 'human_staff';
  readonly text: string;
  readonly isHandoffMarker: boolean;
}

interface ChatRowDto {
  readonly id: string;
  readonly atUtc: string;
  readonly channel: string;
  readonly lastMessageAtUtc: string;
  readonly outcome: string;
  readonly messageCount: number;
  readonly intent: string;
  readonly language: string;
  readonly locationId: string;
  readonly locationName: string | null;
  readonly patientLabel: string | null;
  readonly messages: readonly ChatMessageDto[];
}

export interface LiveChatsSnapshot {
  readonly gated: GatedRows<ChatInteractionView>;
}

interface VobQueueRowDto {
  readonly id: string;
  readonly callId: string;
  readonly payer: string;
  readonly plan: string;
  readonly status: string;
  readonly appointmentId: string | null;
  readonly appointmentStartsAt: string | null;
  readonly assignedTo: string | null;
  readonly requestedAtUtc: string;
  readonly lastAttemptAtUtc: string | null;
  readonly locationId: string;
  readonly locationName: string | null;
  readonly patientFirstName: string | null;
  readonly patientLastName: string | null;
  readonly patientFullName: string | null;
  readonly phoneMasked: string | null;
  readonly priorAuthRequired: boolean;
  readonly referralRequired: boolean;
  readonly ivrNavigationSucceeded: boolean;
  readonly payerRepReached: boolean;
  readonly resolved: boolean;
  readonly resolvedReason: string | null;
  readonly benefits: {
    readonly copayUsd: number | null;
    readonly deductibleUsd: number | null;
    readonly outOfPocketMaxUsd: number | null;
    readonly coverageNotes: string | null;
  };
  readonly attempts: readonly {
    readonly at: string;
    readonly durationSeconds: number;
    readonly outcome: string;
    readonly interactionId: string | null;
    readonly payerReferenceNumber: string | null;
  }[];
  readonly statusTimeline: readonly { readonly at: string; readonly status: string; readonly actor: string; readonly note?: string }[];
  readonly staffNotes: readonly { readonly at: string; readonly author: string; readonly body: string }[];
  readonly callMedia: {
    readonly callId: string;
    readonly at: string;
    readonly durationSeconds: number;
    readonly recordingUrl: string | null;
    readonly transcript: readonly CallTranscriptTurnDto[] | null;
    readonly summary: string | null;
    readonly phoneMasked: string | null;
    readonly patientFirstName: string | null;
    readonly patientLastName: string | null;
  } | null;
}

export interface VobStatsDto {
  readonly inProgress: number;
  readonly inProgressBySubStatus: {
    readonly queued: number;
    readonly dialing: number;
    readonly on_call: number;
    readonly pending_callback: number;
  };
  readonly completedToday: number;
  readonly completedThisWeek: number;
  readonly verifiedRateThisWeek: number | null;
  readonly overviewNeedsAttention: number;
  readonly worklistNeedsAttention: number;
  readonly distributionByGroup: {
    readonly verified: number;
    readonly pending: number;
    readonly needs_attention: number;
  };
}

export interface LiveVobQueueSnapshot {
  readonly gated: GatedRows<VobRecordView>;
  readonly embeddedCalls: ReadonlyMap<string, CallInteractionView>;
  readonly stats: VobStatsDto;
}

export interface LiveEscalation {
  readonly record: Escalation;
  readonly patientName: string;
  readonly locationName: string | null;
}

const LIVE_LOCATION_ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** Only pass real Supabase location UUIDs to the API (mock org ids like loc_north are ignored). */
function liveLocationId(session: Session): string | null {
  if (!session.locationId) return null;
  return LIVE_LOCATION_ID_RE.test(session.locationId) ? session.locationId : null;
}

function applyLocationParam(params: URLSearchParams, session: Session): void {
  const locationId = liveLocationId(session);
  if (locationId) params.set('location_id', locationId);
}

function apiHeaders(session: Session): HeadersInit {
  return {
    'x-actor': session.actor,
    'x-role': session.role,
    'x-mode': session.mode,
  };
}

async function dashboardGet<T>(session: Session, params: URLSearchParams): Promise<T> {
  const response = await fetch(`/api/dashboard?${params.toString()}`, {
    method: 'GET',
    headers: apiHeaders(session),
    cache: 'no-store',
  });
  const payload = await response.json().catch(() => null) as { data?: T; error?: { message?: string } } | null;
  if (!response.ok || !payload || !('data' in payload)) {
    throw new Error(payload?.error?.message ?? `Dashboard API request failed (${response.status})`);
  }
  return payload.data as T;
}

async function dashboardPost<T>(session: Session, body: Record<string, unknown>): Promise<T> {
  const response = await fetch('/api/dashboard', {
    method: 'POST',
    headers: { ...apiHeaders(session), 'content-type': 'application/json' },
    body: JSON.stringify(body),
    cache: 'no-store',
  });
  const payload = await response.json().catch(() => null) as { data?: T; error?: { message?: string } } | null;
  if (!response.ok || !payload || !('data' in payload)) {
    throw new Error(payload?.error?.message ?? `Dashboard API action failed (${response.status})`);
  }
  return payload.data as T;
}

function enumOr<T extends readonly string[]>(values: T, value: string, fallback: T[number]): T[number] {
  return (values as readonly string[]).includes(value) ? value as T[number] : fallback;
}

function validVobStatus(value: string | null): VobStatus | null {
  if (value === null) return null;
  if ((VOB_STATUSES as readonly string[]).includes(value)) return value as VobStatus;
  if (value === 'collecting') return 'queued';
  if (value === 'in_progress') return 'on_call';
  if (value === 'retry_needed') return 'pending_callback';
  if (value === 'missing_information') return 'member_not_found';
  if (value === 'failed_call') return 'unable_to_verify';
  return null;
}

function validResolveReason(value: string | null): VobResolveReason | null {
  if (value === null) return null;
  return (VOB_RESOLVE_REASONS as readonly string[]).includes(value) ? value as VobResolveReason : 'other';
}

function mapEmbeddedCall(
  media: NonNullable<VobQueueRowDto['callMedia']>,
  locationId: string,
): CallInteractionView {
  const identity = fullNameParts(media.patientFirstName, media.patientLastName);
  const hasRecording = hasRecordingSource(media.callId, media.recordingUrl);
  const recordingUrl = hasRecording ? recordingProxyUrl(media.callId) : '';
  const transcript = media.transcript ?? [];
  const callMedia = transcript.length === 0 && !hasRecording
    ? null
    : {
        recordingUrl,
        transcript: transcript.map((turn) => ({ ...turn, redactions: [] })),
        consentDisclosureAtUtc: null,
      };

  return {
    id: media.callId,
    kind: 'call',
    atUtc: media.at,
    direction: 'outbound',
    agent: 'vob',
    contactId: media.callId,
    durationSeconds: media.durationSeconds,
    disposition: 'info_only',
    triage: 'none',
    grade: null,
    locationId,
    locationName: null,
    media: callMedia,
    firstAudioResponseMs: 0,
    costUsd: 0,
    linked: { appointmentId: null, vobId: null, reviewRequestId: null, campaignId: null },
    contact: identity
      ? {
          id: media.callId,
          identity: {
            firstName: identity.firstName,
            lastName: identity.lastName,
            phoneMasked: media.phoneMasked ?? '(***) ***----',
            phoneE164: null,
          },
          insurance: null,
          serviceInterest: media.summary ?? 'VOB call',
          language: 'en',
          locationId,
          consentBasis: null,
          suppressed: false,
        }
      : null,
  };
}

function mapVobRecord(row: VobQueueRowDto): VobRecordView {
  const status = validVobStatus(row.status) ?? 'queued';
  const identity = fullNameParts(row.patientFirstName, row.patientLastName, row.patientFullName);
  const phoneMasked = row.phoneMasked ?? '(---) --- ----';

  return {
    id: row.id,
    contactId: row.id,
    payer: row.payer,
    plan: row.plan,
    status,
    appointmentId: row.appointmentId,
    assignedTo: row.assignedTo,
    requestedAtUtc: row.requestedAtUtc,
    lastAttemptAtUtc: row.lastAttemptAtUtc,
    attempts: row.attempts.map((attempt) => ({
      at: attempt.at,
      durationSeconds: attempt.durationSeconds,
      outcome: attempt.outcome,
      interactionId: attempt.interactionId,
      payerReferenceNumber: attempt.payerReferenceNumber,
    })),
    benefits: {
      copayUsd: row.benefits.copayUsd,
      deductibleUsd: row.benefits.deductibleUsd,
      outOfPocketMaxUsd: row.benefits.outOfPocketMaxUsd,
      coverageNotes: row.benefits.coverageNotes,
    },
    priorAuthRequired: row.priorAuthRequired,
    referralRequired: row.referralRequired,
    ivrNavigationSucceeded: row.ivrNavigationSucceeded,
    payerRepReached: row.payerRepReached,
    locationId: row.locationId,
    locationName: row.locationName ?? null,
    resolvedReason: validResolveReason(row.resolvedReason),
    resolved: row.resolved,
    staffNotes: row.staffNotes,
    statusTimeline: row.statusTimeline
      .map((entry) => {
        const entryStatus = validVobStatus(entry.status);
        if (!entryStatus) return null;
        return { at: entry.at, status: entryStatus, actor: entry.actor };
      })
      .filter((entry): entry is { at: string; status: VobStatus; actor: string } => entry !== null),
    contact: {
      id: row.id,
      identity: identity
        ? { ...identity, phoneMasked, phoneE164: null }
        : null,
      insurance: null,
      serviceInterest: row.plan,
      language: 'en',
      locationId: row.locationId,
      consentBasis: null,
      suppressed: false,
    },
  };
}

function validConfirmationOutcome(value: string): ConfirmationAttemptOutcome {
  return enumOr(CONFIRMATION_ATTEMPT_OUTCOMES, value, 'reached');
}

function validCallDisposition(value: string): CallDisposition {
  return enumOr(CALL_DISPOSITIONS, value, 'info_only') as CallDisposition;
}

function fullNameParts(first: string | null, last: string | null, fullName?: string | null): { firstName: string; lastName: string } | null {
  const full = (fullName ?? '').trim();
  if (full) {
    const parts = full.split(/\s+/);
    return { firstName: parts[0] || 'Unknown', lastName: parts.slice(1).join(' ') };
  }
  const f = (first ?? '').trim();
  const l = (last ?? '').trim();
  if (!f && !l) return null;
  return { firstName: f || 'Unknown', lastName: l };
}

function mapAppointment(row: AppointmentRowDto): AppointmentView {
  const identity = fullNameParts(row.patient.firstName, row.patient.lastName, row.patient.fullName);
  const startsAt = row.startsAt ?? row.bookedAt ?? row.createdAt;
  const phoneMasked = row.patient.phoneMasked ?? '(---) --- ----';

  return {
    id: row.id,
    contactId: row.patientId,
    startsAtUtc: startsAt,
    serviceInterest: row.serviceInterest || row.appointmentTextRaw || 'Appointment',
    source: enumOr(APPOINTMENT_SOURCES, row.source, 'voice') as AppointmentSource,
    language: enumOr(LANGUAGES, row.language, 'en') as Language,
    insuranceCaptured: row.insuranceCaptured,
    vobId: validVobStatus(row.vobStatus) && row.vobId ? row.vobId : null,
    triage: enumOr(TRIAGE_FLAGS, row.triage, 'none') as TriageFlag,
    status: enumOr(APPOINTMENT_STATUSES, row.status, 'booked') as AppointmentStatus,
    bookedByAgent: enumOr(AGENT_IDS, row.bookedByAgent, 'receptionist') as AgentId,
    bookedAtUtc: row.bookedAt ?? row.createdAt,
    locationId: row.locationId,
    locationName: row.locationName ?? null,
    afterHours: row.afterHours,
    originatingInteractionId: row.callId,
    timeline: row.timeline.map((event) => ({ at: event.at, label: event.label, actor: event.actor })),
    confirmationAttempts: row.confirmationAttempts.map((attempt) => ({
      at: attempt.at,
      outcome: validConfirmationOutcome(attempt.outcome),
    })),
    staffNotes: row.staffNotes.map((note) => ({ at: note.at, author: note.author, body: note.body })),
    needsReview: row.needsReview,
    hasScheduledTime: row.startsAt !== null,
    contact: {
      id: row.patientId,
      identity: identity
        ? { ...identity, phoneMasked, phoneE164: row.patient.phoneE164 }
        : null,
      insurance: null,
      serviceInterest: row.serviceInterest || row.appointmentTextRaw || 'Appointment',
      language: enumOr(LANGUAGES, row.language, 'en') as Language,
      locationId: row.locationId,
      consentBasis: null,
      suppressed: false,
    },
  };
}

function mapEscalation(row: EscalationRowDto): LiveEscalation {
  const patient = fullNameParts(row.patient?.firstName ?? null, row.patient?.lastName ?? null);
  const patientName = patient ? `${patient.firstName} ${patient.lastName}`.trim() : 'Unknown patient';
  const trigger = enumOr(ESCALATION_TRIGGERS, row.trigger, 'agent_initiated') as EscalationTrigger;
  const status = enumOr(ESCALATION_STATUSES, row.status, 'open') as EscalationStatus;

  return {
    patientName,
    locationName: row.locationName,
    record: {
      id: row.id,
      atUtc: row.createdAt,
      contactId: row.patientId ?? row.id,
      sourceInteractionId: row.callId ?? row.id,
      trigger,
      routedTo: row.routedTo ?? '-',
      status,
      acknowledgedAtUtc: row.acknowledgedAt,
      acknowledgedBy: row.acknowledgedBy,
      resolutionNote: row.resolutionNote,
      locationId: row.locationId,
    },
  };
}

export function mapDashboardStatsToAppointmentStats(stats: DashboardStatsDto): AppointmentStats {
  return {
    bookedToday: stats.bookedToday,
    bookedSameWeekdayLastWeek: stats.bookedSameWeekdayLastWeek,
    bookedThisWeek: stats.bookedThisWeek,
    bookingRateThisWeek: stats.bookingRateThisWeek,
    upcomingNext7Days: stats.upcomingNext7Days,
    noShowsAndCancellationsThisWeek: stats.noShowsAndCancellationsThisWeek,
    noShowCancelRateThisWeek: stats.noShowCancelRateThisWeek,
    confirmationRate: stats.confirmationRate,
    noShowRate30d: stats.noShowRate30d,
  };
}

export async function fetchLiveAppointments(session: Session): Promise<LiveAppointmentsSnapshot> {
  const params = new URLSearchParams({ resource: 'appointments', limit: '1000' });
  const statsParams = new URLSearchParams({ resource: 'stats' });
  applyLocationParam(params, session);
  applyLocationParam(statsParams, session);

  const [list, stats] = await Promise.all([
    dashboardGet<{ rows?: readonly AppointmentRowDto[]; total: number; kind?: 'aggregate' }>(session, params),
    dashboardGet<DashboardStatsDto>(session, statsParams),
  ]);

  if (list.kind === 'aggregate') {
    return { gated: { kind: 'aggregate', total: list.total, reason: 'NON_PHI_MODE' }, stats, vobStatusById: new Map() };
  }

  const rows = (list.rows ?? []).map(mapAppointment);
  const vobStatusById = new Map<string, VobStatus>();
  for (const row of list.rows ?? []) {
    const status = validVobStatus(row.vobStatus);
    if (row.vobId && status) vobStatusById.set(row.vobId, status);
  }

  return { gated: { kind: 'rows', rows }, stats, vobStatusById };
}

export async function fetchLiveEscalationStats(session: Session): Promise<EscalationStatsDto> {
  return dashboardGet<EscalationStatsDto>(session, new URLSearchParams({ resource: 'escalation_stats' }));
}

function mapCall(row: CallRowDto): CallInteractionView {
  const identity = fullNameParts(row.patient.firstName, row.patient.lastName, row.patient.fullName);
  const locationId = row.locationId ?? 'fd8bf778-6eb2-4da0-99ee-12280158fb75';
  const hasRecording = hasRecordingSource(row.callId, row.recordingUrl);
  const recordingUrl = hasRecording ? recordingProxyUrl(row.callId) : '';
  const transcript = row.transcript ?? [];
  const media = row.transcript === null && !hasRecording
    ? null
    : {
        recordingUrl,
        transcript: transcript.map((turn) => ({ ...turn, redactions: [] })),
        consentDisclosureAtUtc: null,
      };
  return {
    id: row.id,
    kind: 'call',
    atUtc: row.at,
    direction: row.direction,
    agent: row.agent,
    contactId: row.callId,
    durationSeconds: row.durationSeconds,
    disposition: validCallDisposition(row.disposition),
    triage: enumOr(TRIAGE_FLAGS, row.triage, 'none') as TriageFlag,
    grade: null,
    locationId,
    locationName: row.locationName,
    callbackNumberMasked: row.callbackNumberMasked,
    media,
    firstAudioResponseMs: 0,
    costUsd: 0,
    linked: { appointmentId: null, vobId: null, reviewRequestId: null, campaignId: null },
    contact: identity
      ? {
          id: row.callId,
          identity: {
            firstName: identity.firstName,
            lastName: identity.lastName,
            phoneMasked: row.patient.phoneMasked ?? '(***) ***----',
            phoneE164: null,
          },
          insurance: null,
          serviceInterest: row.summary ?? 'Call',
          language: 'en',
          locationId,
          consentBasis: null,
          suppressed: false,
        }
      : null,
  };
}

export async function fetchLiveCalls(session: Session): Promise<LiveCallsSnapshot> {
  const params = new URLSearchParams({ resource: 'calls', limit: '100' });
  applyLocationParam(params, session);
  const list = await dashboardGet<{ rows?: readonly CallRowDto[]; total: number; kind?: 'aggregate' }>(session, params);
  if (list.kind === 'aggregate') {
    return { gated: { kind: 'aggregate', total: list.total, reason: 'NON_PHI_MODE' } };
  }
  return { gated: { kind: 'rows', rows: (list.rows ?? []).map(mapCall) } };
}

const CHAT_OUTCOMES = ['contained', 'resolved', 'escalated', 'booked'] as const;

function mapChat(row: ChatRowDto, session: Session): ChatInteractionView {
  const label = row.patientLabel?.trim() ?? '';
  const nameParts = label.split(/\s+/).filter(Boolean);
  const firstName = nameParts[0] ?? '';
  const lastName = nameParts.length > 1 ? nameParts.slice(1).join(' ') : '';
  const messages = canAccessMedia(session)
    ? row.messages.map((msg) => ({
        at: msg.at,
        speaker: msg.speaker,
        text: msg.text,
        isHandoffMarker: msg.isHandoffMarker,
      }))
    : null;

  return {
    id: row.id,
    kind: 'chat',
    atUtc: row.atUtc,
    channel: row.channel === 'whatsapp' ? 'whatsapp' : 'web_chat',
    contactId: null,
    lastMessageAtUtc: row.lastMessageAtUtc,
    outcome: enumOr(CHAT_OUTCOMES, row.outcome, 'contained') as ChatInteractionView['outcome'],
    messageCount: row.messageCount,
    intent: row.intent,
    language: enumOr(LANGUAGES, row.language, 'en') as Language,
    locationId: row.locationId,
    responseLatencyMs: 0,
    grade: null,
    linked: { appointmentId: null },
    messages,
    contact: label
      ? {
          id: row.id,
          identity: {
            firstName,
            lastName,
            phoneMasked: '(***) ***----',
            phoneE164: null,
          },
          insurance: null,
          serviceInterest: row.intent,
          language: enumOr(LANGUAGES, row.language, 'en') as Language,
          locationId: row.locationId,
          consentBasis: null,
          suppressed: false,
        }
      : null,
  };
}

export async function fetchLiveChats(session: Session): Promise<LiveChatsSnapshot> {
  const params = new URLSearchParams({ resource: 'chats', limit: '100' });
  applyLocationParam(params, session);
  const list = await dashboardGet<{ rows?: readonly ChatRowDto[]; total: number; kind?: 'aggregate' }>(session, params);
  if (list.kind === 'aggregate') {
    return { gated: { kind: 'aggregate', total: list.total, reason: 'NON_PHI_MODE' } };
  }
  return { gated: { kind: 'rows', rows: (list.rows ?? []).map((row) => mapChat(row, session)) } };
}

export interface LiveNotificationCounts {
  readonly total: number;
  readonly escalationsPending: number;
  readonly vobPendingCalls: number;
}

export async function fetchLiveNotifications(session: Session): Promise<LiveNotificationCounts> {
  const params = new URLSearchParams({ resource: 'notifications' });
  applyLocationParam(params, session);
  const data = await dashboardGet<LiveNotificationCounts>(session, params);
  return {
    total: data.total ?? 0,
    escalationsPending: data.escalationsPending ?? 0,
    vobPendingCalls: data.vobPendingCalls ?? 0,
  };
}

export async function fetchLiveEscalations(session: Session): Promise<LiveEscalationsSnapshot> {
  const params = new URLSearchParams({ resource: 'escalations', limit: '1000' });
  applyLocationParam(params, session);

  const [list, stats] = await Promise.all([
    dashboardGet<{ rows?: readonly EscalationRowDto[]; total: number; kind?: 'aggregate' }>(session, params),
    fetchLiveEscalationStats(session),
  ]);

  if (list.kind === 'aggregate') {
    return { gated: { kind: 'aggregate', total: list.total, reason: 'NON_PHI_MODE' }, stats };
  }

  return { gated: { kind: 'rows', rows: (list.rows ?? []).map(mapEscalation) }, stats };
}

export async function acknowledgeLiveEscalation(session: Session, escalationId: string): Promise<void> {
  await dashboardPost(session, { action: 'acknowledge_escalation', escalationId });
}

export async function saveLiveEscalationNote(session: Session, escalationId: string, body: string): Promise<void> {
  await dashboardPost(session, { action: 'escalation_note', escalationId, body });
}

export async function updateLiveAppointmentStatus(
  session: Session,
  appointmentId: string,
  status: AppointmentStatus,
): Promise<void> {
  await dashboardPost(session, { action: 'status_change', appointmentId, status });
}

export async function addLiveAppointmentNote(session: Session, appointmentId: string, body: string): Promise<void> {
  await dashboardPost(session, { action: 'add_note', appointmentId, body });
}

export async function recordLivePatientSearch(session: Session, query: string): Promise<void> {
  await dashboardPost(session, { action: 'record_search', query });
}

export function mapVobStatsToCounts(stats: VobStatsDto): VobCounts {
  return {
    inProgress: stats.inProgress,
    inProgressBySubStatus: stats.inProgressBySubStatus,
    completedToday: stats.completedToday,
    completedThisWeek: stats.completedThisWeek,
    verifiedRateThisWeek: stats.verifiedRateThisWeek,
    overviewNeedsAttention: stats.overviewNeedsAttention,
    worklistNeedsAttention: stats.worklistNeedsAttention,
  };
}

export async function fetchLiveVobQueue(session: Session): Promise<LiveVobQueueSnapshot> {
  const params = new URLSearchParams({ resource: 'vob_queue', limit: '1000' });
  const statsParams = new URLSearchParams({ resource: 'vob_stats' });
  applyLocationParam(params, session);
  applyLocationParam(statsParams, session);

  const [list, stats] = await Promise.all([
    dashboardGet<{ rows?: readonly VobQueueRowDto[]; total: number; kind?: 'aggregate' }>(session, params),
    dashboardGet<VobStatsDto>(session, statsParams),
  ]);

  if (list.kind === 'aggregate') {
    return { gated: { kind: 'aggregate', total: list.total, reason: 'NON_PHI_MODE' }, embeddedCalls: new Map(), stats };
  }

  const embeddedCalls = new Map<string, CallInteractionView>();
  const rows = (list.rows ?? []).map((row) => {
    if (row.callMedia) {
      embeddedCalls.set(row.callMedia.callId, mapEmbeddedCall(row.callMedia, row.locationId));
    }
    return mapVobRecord(row);
  });

  return { gated: { kind: 'rows', rows }, embeddedCalls, stats };
}

export async function retryLiveVob(session: Session, vobId: string): Promise<void> {
  await dashboardPost(session, { action: 'vob_retry', vobId });
}

export async function resolveLiveVob(session: Session, vobId: string, reason: VobResolveReason): Promise<void> {
  await dashboardPost(session, { action: 'vob_resolve', vobId, reason });
}

export async function escalateLiveVob(session: Session, vobId: string, assignee: string): Promise<void> {
  await dashboardPost(session, { action: 'vob_escalate', vobId, assignee });
}

export async function addLiveVobNote(session: Session, vobId: string, body: string): Promise<void> {
  await dashboardPost(session, { action: 'vob_add_note', vobId, body });
}

export interface RuntimeSettingsDto {
  readonly useGroqTableFill: boolean;
}

export async function fetchRuntimeSettings(session: Session): Promise<RuntimeSettingsDto> {
  return dashboardGet<RuntimeSettingsDto>(session, new URLSearchParams({ resource: 'runtime_settings' }));
}

export async function setRuntimeSettings(session: Session, useGroqTableFill: boolean): Promise<RuntimeSettingsDto> {
  return dashboardPost<RuntimeSettingsDto>(session, {
    action: 'set_runtime_settings',
    useGroqTableFill,
  });
}

