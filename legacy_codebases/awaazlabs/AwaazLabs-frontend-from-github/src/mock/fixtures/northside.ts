/**
 * NORTHSIDE DENTAL GROUP — the rich, multi-location demo fixture (§ spec, PHI-BAA tier).
 *
 * Everything here is deterministic and anchored to MOCK_NOW_UTC. Cross-references
 * (appointment ↔ VOB ↔ call ↔ campaign ↔ review) are wired at construction time from
 * predetermined id ranges, so referential integrity holds without post-hoc mutation.
 *
 * Interpretations (narrowest reading of the spec; recorded here and in the return summary):
 *  - N1: §10.1 lists five *voice* agents for the Calls table (Receptionist, VOB, Verifier,
 *    Review Taker, Reengagement). The `chat` AgentId is a text agent and is exercised via
 *    `chats`, never via a call row — a call with agent `chat` would contradict §10.1.
 *    Every AgentId is therefore represented across the interaction set as a whole.
 *  - N2: "booking calls" are the only calls that set `linked.appointmentId`; per §10.1 that
 *    field is "appointment created". Confirmation (Verifier) calls relate to an appointment
 *    but did not create it, so their `linked.appointmentId` is null. This keeps the
 *    appointment ↔ originating-interaction link exactly bidirectional.
 */

import { MOCK_NOW_UTC, NORTHSIDE_DENTAL } from '@/mock/orgs';
import type {
  AgentRegistryEntry,
  Appointment,
  AppointmentTimelineEvent,
  CallInteraction,
  Campaign,
  CampaignContact,
  ChatInteraction,
  ChatMessage,
  ConfirmationAttempt,
  Escalation,
  FlaggedInteraction,
  InteractionMedia,
  Invoice,
  KnowledgeBlock,
  KnowledgeChangeRequest,
  Member,
  OptimizationEvent,
  OrgFixture,
  PatientContact,
  PhoneLine,
  PrivateFeedback,
  PublishedReview,
  ReviewRequest,
  SuppressionEntry,
  VobAttempt,
  VobRecord,
} from '@/mock/schema';
import type {
  AppointmentSource,
  AppointmentStatus,
  CallDisposition,
  ChatChannel,
  ConfirmationAttemptOutcome,
  Language,
  TriageFlag,
  VobStatus,
} from '@/shared/status-models';
import {
  addMinutes,
  addSeconds,
  ageHours,
  atLocalHour,
  daysAgo,
  fictionPhone,
  hoursAgo,
  makeGrade,
  makePrng,
  minutesAgo,
  pad,
  turn,
  type RedactPhrase,
} from './helpers';

const ORG_ID = NORTHSIDE_DENTAL.id;
const rng = makePrng(0xa1b2c3d4);

const LOC_NORTH = 'loc_north';
const LOC_WEST = 'loc_west';
const LOC_SOUTH = 'loc_south';

const TZ_BY_LOC: Readonly<Record<string, string>> = {
  [LOC_NORTH]: 'America/Chicago',
  [LOC_WEST]: 'America/Chicago',
  [LOC_SOUTH]: 'America/Denver',
};

/** The optimization deployment that lifts Receptionist grades (§12.2 / §19). */
const RECEPTIONIST_DEPLOY_DAYS_AGO = 20;
const RECEPTIONIST_VERIFY_DAYS_AGO = 6;

/* ==================================================================================
 * Agent registry (§2.6) — six standard agents + one custom, proving zero-frontend render
 * ================================================================================== */

const AGENTS: readonly AgentRegistryEntry[] = [
  {
    id: 'receptionist',
    name: 'Receptionist',
    type: 'inbound',
    channel: 'voice',
    icon: 'Headset',
    isCustom: false,
    slug: 'receptionist',
    metricsContract: [
      { key: 'bookings', label: 'Appointments booked', format: 'count' },
      { key: 'booking_rate', label: 'Booking rate', format: 'percent', description: 'Booked / completed inbound calls' },
      { key: 'safety_escalation_rate', label: 'Safety escalation rate', format: 'percent' },
      { key: 'insurance_capture_rate', label: 'Insurance capture rate', format: 'percent' },
      { key: 'after_hours_share', label: 'After-hours share of bookings', format: 'percent' },
      { key: 'avg_handle_time', label: 'Avg booking handle time', format: 'duration_s' },
    ],
  },
  {
    id: 'vob',
    name: 'VOB Agent',
    type: 'outbound',
    channel: 'voice',
    icon: 'ShieldCheck',
    isCustom: false,
    slug: 'vob-agent',
    metricsContract: [
      { key: 'verifications', label: 'Verifications', format: 'count' },
      { key: 'verified_rate', label: 'Verified rate', format: 'percent' },
      { key: 'ivr_success', label: 'IVR navigation success', format: 'percent' },
      { key: 'benefit_capture', label: 'Benefit capture completeness', format: 'percent' },
      { key: 'avg_handle_time', label: 'Avg handle time per call', format: 'duration_s' },
    ],
  },
  {
    id: 'verifier',
    name: 'Verifier',
    type: 'outbound',
    channel: 'voice',
    icon: 'CalendarDays',
    isCustom: false,
    slug: 'verifier',
    metricsContract: [
      { key: 'confirmation_attempts', label: 'Confirmation attempts', format: 'count' },
      { key: 'confirmed_rate', label: 'Confirmed rate', format: 'percent' },
      { key: 'reschedule_rate', label: 'Reschedule-requested rate', format: 'percent' },
    ],
  },
  {
    id: 'chat',
    name: 'Chat Agents',
    type: 'inbound',
    channel: 'chat',
    icon: 'MessageSquare',
    isCustom: false,
    slug: 'chat-agents',
    metricsContract: [
      { key: 'sessions', label: 'Sessions', format: 'count' },
      { key: 'containment_rate', label: 'Containment rate', format: 'percent' },
      { key: 'resolution_rate', label: 'Resolution rate', format: 'percent' },
      { key: 'response_latency', label: 'Avg response latency', format: 'duration_ms' },
    ],
  },
  {
    id: 'review_taker',
    name: 'Review Taker',
    type: 'outbound',
    channel: 'voice',
    icon: 'Star',
    isCustom: false,
    slug: 'review-taker',
    metricsContract: [
      { key: 'reach_rate', label: 'Reach rate', format: 'percent' },
      { key: 'agreement_rate', label: 'Agreement rate', format: 'percent' },
      { key: 'reviews_posted', label: 'Reviews posted (attributed)', format: 'count' },
      { key: 'avg_rating', label: 'Average attributed rating', format: 'count' },
    ],
  },
  {
    id: 'reengagement',
    name: 'Reengagement',
    type: 'outbound',
    channel: 'voice',
    icon: 'PhoneOutgoing',
    isCustom: false,
    slug: 'reengagement',
    metricsContract: [
      { key: 'reach_rate', label: 'Reach rate', format: 'percent' },
      { key: 'bookings', label: 'Bookings generated', format: 'count' },
      { key: 'revenue_estimate', label: 'Revenue estimate', format: 'currency_usd' },
    ],
  },
  {
    // §2.6 custom enterprise agent — renders through the standard template with zero
    // frontend work. Proves the registry-driven page.
    id: 'post_op_followup',
    name: 'Post-Op Follow-Up',
    type: 'outbound',
    channel: 'voice',
    icon: 'ClipboardCheck',
    isCustom: true,
    slug: 'post-op-followup',
    metricsContract: [
      { key: 'followups_placed', label: 'Follow-ups placed', format: 'count' },
      { key: 'reached_rate', label: 'Reached rate', format: 'percent' },
      { key: 'complications_flagged', label: 'Complications flagged to staff', format: 'count' },
    ],
  },
];

/* ==================================================================================
 * Contacts (§2.5) — ~60, diverse & fictional, en-heavy with meaningful es share
 * ================================================================================== */

interface NameSpec {
  readonly first: string;
  readonly last: string;
  readonly lang: Language;
}

const NAME_SPECS: readonly NameSpec[] = [
  { first: 'Emily', last: 'Carter', lang: 'en' },
  { first: 'James', last: 'Whitfield', lang: 'en' },
  { first: 'Olivia', last: 'Bennett', lang: 'en' },
  { first: 'Michael', last: 'Thompson', lang: 'en' },
  { first: 'Sophia', last: 'Reed', lang: 'en' },
  { first: 'William', last: 'Hayes', lang: 'en' },
  { first: 'Ava', last: 'Coleman', lang: 'en' },
  { first: 'Benjamin', last: 'Foster', lang: 'en' },
  { first: 'Charlotte', last: 'Price', lang: 'en' },
  { first: 'Daniel', last: 'Brooks', lang: 'en' },
  { first: 'Grace', last: 'Sullivan', lang: 'en' },
  { first: 'Henry', last: 'Dawson', lang: 'en' },
  { first: 'Lily', last: 'Morgan', lang: 'en' },
  { first: 'Jack', last: 'Turner', lang: 'en' },
  { first: 'Chloe', last: 'Hamilton', lang: 'en' },
  { first: 'Owen', last: 'Fletcher', lang: 'en' },
  { first: 'Zoe', last: 'Palmer', lang: 'en' },
  { first: 'Nathan', last: 'Ellis', lang: 'en' },
  { first: 'Hannah', last: 'Barlow', lang: 'en' },
  { first: 'Samuel', last: 'Grant', lang: 'en' },
  { first: 'Ruby', last: 'Lawson', lang: 'en' },
  { first: 'Caleb', last: 'Norton', lang: 'en' },
  { first: 'Ella', last: 'Warren', lang: 'en' },
  { first: 'Isaac', last: 'Bishop', lang: 'en' },
  { first: 'Nora', last: 'Chapman', lang: 'en' },
  { first: 'Aaron', last: 'Webb', lang: 'en' },
  { first: 'Mia', last: 'Sanders', lang: 'en' },
  { first: 'Leo', last: 'Barrett', lang: 'en' },
  { first: 'Aria', last: 'Fox', lang: 'en' },
  { first: 'Julian', last: 'Pierce', lang: 'en' },
  { first: 'Sadie', last: 'Hunt', lang: 'en' },
  { first: 'Miles', last: 'Ashford', lang: 'en' },
  { first: 'Iris', last: 'Cross', lang: 'en' },
  { first: 'Oscar', last: 'Vaughn', lang: 'en' },
  { first: 'Elena', last: 'Marsh', lang: 'en' },
  { first: 'Felix', last: 'Doyle', lang: 'en' },
  { first: 'Clara', last: 'Osborne', lang: 'en' },
  { first: 'Theo', last: 'Sharpe', lang: 'en' },
  { first: 'Maya', last: 'Frost', lang: 'en' },
  { first: 'Simon', last: 'Wren', lang: 'en' },
  { first: 'Valentina', last: 'Reyes', lang: 'es' },
  { first: 'Mateo', last: 'Guzman', lang: 'es' },
  { first: 'Camila', last: 'Herrera', lang: 'es' },
  { first: 'Diego', last: 'Fuentes', lang: 'es' },
  { first: 'Isabella', last: 'Navarro', lang: 'es' },
  { first: 'Santiago', last: 'Molina', lang: 'es' },
  { first: 'Lucia', last: 'Delgado', lang: 'es' },
  { first: 'Emiliano', last: 'Castillo', lang: 'es' },
  { first: 'Renata', last: 'Vega', lang: 'es' },
  { first: 'Andres', last: 'Salazar', lang: 'es' },
  { first: 'Ximena', last: 'Rios', lang: 'es' },
  { first: 'Joaquin', last: 'Mendez', lang: 'es' },
  { first: 'Gabriela', last: 'Ortega', lang: 'es' },
  { first: 'Tomas', last: 'Aguilar', lang: 'es' },
  { first: 'Daniela', last: 'Cordova', lang: 'es' },
  { first: 'Aarav', last: 'Patel', lang: 'other' },
  { first: 'Mei-Lin', last: 'Chen', lang: 'other' },
  { first: 'Yusuf', last: 'Demir', lang: 'other' },
  { first: 'Anaya', last: 'Okafor', lang: 'other' },
  { first: 'Nikolai', last: 'Volkov', lang: 'other' },
];

const SERVICE_INTERESTS: readonly string[] = [
  'New patient exam',
  'Cleaning',
  'Crown',
  'Root canal',
  'Implant consult',
  'Teeth whitening',
  'Braces consult',
  'Filling',
  'Extraction',
  'Denture fitting',
  'Pediatric checkup',
  'Emergency toothache',
];

const CARRIERS: readonly { readonly carrier: string; readonly plan: string }[] = [
  { carrier: 'Aetna', plan: 'PPO Dental Plus' },
  { carrier: 'BCBS', plan: 'Blue Choice Dental' },
  { carrier: 'Cigna', plan: 'Dental 1500' },
  { carrier: 'UnitedHealthcare', plan: 'Dental Core' },
  { carrier: 'Humana', plan: 'Complete Dental' },
  { carrier: 'Delta Dental', plan: 'PPO Premier' },
];

const LOC_CYCLE: readonly string[] = [LOC_NORTH, LOC_NORTH, LOC_WEST, LOC_SOUTH, LOC_NORTH];
const SUPPRESSED_IDX = new Set<number>([2, 11, 26, 43, 50, 57]);
const NO_INSURANCE_IDX = new Set<number>([5, 16, 28, 35, 47, 54, 56, 59]);

const contacts: PatientContact[] = NAME_SPECS.map((spec, i): PatientContact => {
  const id = `c_ns_${pad(i + 1)}`;
  const locationId = LOC_CYCLE[i % LOC_CYCLE.length];
  const serviceInterest = SERVICE_INTERESTS[i % SERVICE_INTERESTS.length];
  const hasInsurance = !NO_INSURANCE_IDX.has(i);
  const carrier = CARRIERS[i % CARRIERS.length];
  const suppressed = SUPPRESSED_IDX.has(i);
  return {
    id,
    identity: {
      firstName: spec.first,
      lastName: spec.last,
      phoneE164: fictionPhone(2000 + i),
    },
    insurance: hasInsurance
      ? {
          carrier: carrier.carrier,
          plan: carrier.plan,
          memberIdMasked: `••••${pad(4200 + i, 4)}`,
          groupNumber: i % 3 === 0 ? null : `GRP-${pad(100 + i)}`,
        }
      : null,
    serviceInterest,
    language: spec.lang,
    locationId,
    consentBasis: suppressed ? 'Patient opt-out recorded' : 'Existing patient relationship',
    suppressed,
  };
});

const contactById = new Map(contacts.map((c) => [c.id, c]));
function contactOf(id: string): PatientContact {
  const c = contactById.get(id);
  if (!c) throw new Error(`northside fixture: unknown contact ${id}`);
  return c;
}
function contactFirst(id: string): string {
  return contactOf(id).identity?.firstName ?? 'the caller';
}

/* ==================================================================================
 * Appointments (§5) — 120, MOCK_NOW −45d → +14d, all statuses & sources
 * ================================================================================== */

const SOURCE_CYCLE: readonly AppointmentSource[] = ['voice', 'whatsapp', 'web_chat', 'form', 'voice', 'voice'];

interface StatusBucket {
  readonly status: AppointmentStatus;
  readonly count: number;
  readonly startFrom: number; // dayOffset range (inclusive)
  readonly startTo: number;
}
const STATUS_BUCKETS: readonly StatusBucket[] = [
  { status: 'completed', count: 52, startFrom: -44, startTo: -1 },
  { status: 'no_show', count: 10, startFrom: -40, startTo: -3 },
  { status: 'cancelled', count: 10, startFrom: -35, startTo: 4 },
  { status: 'rescheduled', count: 8, startFrom: -22, startTo: 9 },
  { status: 'confirmed', count: 22, startFrom: -1, startTo: 9 },
  { status: 'booked', count: 18, startFrom: 1, startTo: 14 },
];

const TOTAL_APPTS = STATUS_BUCKETS.reduce((sum, b) => sum + b.count, 0);

// Recovered no-show pairs (B5): these contacts get a no_show and a later completed appt.
const RECOVERED_CONTACTS: readonly string[] = ['c_ns_005', 'c_ns_014', 'c_ns_042', 'c_ns_050'];

interface ApptDraft {
  readonly id: string;
  readonly index: number;
  readonly contactId: string;
  readonly locationId: string;
  readonly tz: string;
  readonly status: AppointmentStatus;
  readonly startsAtUtc: string;
  readonly bookedAtUtc: string;
  readonly source: AppointmentSource;
  readonly afterHours: boolean;
  readonly triage: TriageFlag;
  originatingInteractionId: string | null;
  vobId: string | null;
}

function spread(from: number, to: number, k: number, n: number): number {
  if (n <= 1) return Math.round((from + to) / 2);
  return Math.round(from + ((to - from) * k) / (n - 1));
}

// Predetermined booking-link counters (see N2).
let voiceBookingCounter = 0;
let chatBookingCounter = 0;
const VOICE_BOOKING_MAX = 15;
const CHAT_BOOKING_MAX = 12;

const apptDrafts: ApptDraft[] = [];
{
  let globalIndex = 0;
  for (const bucket of STATUS_BUCKETS) {
    for (let k = 0; k < bucket.count; k++) {
      const index = globalIndex;
      const id = `a_ns_${pad(index + 1)}`;
      const contactId = contacts[(index * 7 + 3) % contacts.length].id;
      const contact = contactById.get(contactId)!;
      const locationId = contact.locationId;
      const tz = TZ_BY_LOC[locationId];

      const dayOffset = spread(bucket.startFrom, bucket.startTo, k, bucket.count);
      const afterHours = index % 7 === 0;
      const startHour = afterHours ? (dayOffset >= 0 ? 7 : 19) : 9 + (k % 7);
      const startsAtUtc = atLocalHour(dayOffset, startHour, tz, (index % 4) * 15);

      // Emergency / high-acuity service interests carry a real triage flag.
      const svc = contact.serviceInterest;
      let triage: TriageFlag = 'none';
      if (svc === 'Emergency toothache') triage = index % 2 === 0 ? 'urgent' : 'high';
      else if (svc === 'Root canal' || svc === 'Extraction') triage = index % 3 === 0 ? 'high' : 'low';
      else if (index % 9 === 0) triage = 'low';

      // Booked-at: patients book ahead, so the booking date is spread proportionally across
      // the whole 45-day window by index rather than clustered right before the visit — the
      // §4.1 booking-rate denominators would otherwise be starved in the trailing week. It is
      // always strictly in the past and never after the visit it created. Explicit "booked
      // today" and "same weekday last week" cohorts are assigned below (see D3).
      const latestBook = dayOffset >= 0 ? -1 : dayOffset - 1;
      const spread44 = -44 + Math.round((index / (TOTAL_APPTS - 1)) * 43);
      const bookedDayOffset = Math.min(spread44, latestBook);
      const bookedHour = afterHours ? 19 : 9 + (index % 7);
      const bookedAtUtc = atLocalHour(bookedDayOffset, bookedHour, tz, (index % 3) * 20);

      const source = SOURCE_CYCLE[index % SOURCE_CYCLE.length];
      const originatingInteractionId: string | null = null;

      apptDrafts.push({
        id,
        index,
        contactId,
        locationId,
        tz,
        status: bucket.status,
        startsAtUtc,
        bookedAtUtc,
        source,
        afterHours,
        triage,
        originatingInteractionId,
        vobId: null,
      });
      globalIndex++;
    }
  }
}

// Recovered no-show wiring (§4.3 / B5): each recovered contact gets a no_show whose start is
// THIS calendar month, PLUS a later appointment booked AFTER that missed start.
// countRecoveredNoShows scopes to the current month and requires bookedAtUtc > missed
// startsAtUtc, so both facts must hold inside July for the recovery to be counted.
const RECOVERED_NOSHOW_START_OFFSETS: readonly number[] = [-7, -5, -3, -2]; // Jul 2,4,6,7 (UTC)
{
  const noShowDrafts = apptDrafts.filter((d) => d.status === 'no_show').slice(0, RECOVERED_CONTACTS.length);
  noShowDrafts.forEach((d, i) => {
    const c = contactOf(RECOVERED_CONTACTS[i]);
    const tz = TZ_BY_LOC[c.locationId];
    (d as { contactId: string }).contactId = RECOVERED_CONTACTS[i];
    (d as { locationId: string }).locationId = c.locationId;
    (d as { tz: string }).tz = tz;
    (d as { startsAtUtc: string }).startsAtUtc = atLocalHour(RECOVERED_NOSHOW_START_OFFSETS[i], 10, tz, 0);
    (d as { bookedAtUtc: string }).bookedAtUtc = atLocalHour(RECOVERED_NOSHOW_START_OFFSETS[i] - 6, 9, tz, 0);
  });
  // Later appointments (future visits, booked yesterday — after every July no_show start).
  const laterDrafts = apptDrafts.filter((d) => d.status === 'booked').slice(0, RECOVERED_CONTACTS.length);
  laterDrafts.forEach((d, i) => {
    const c = contactOf(RECOVERED_CONTACTS[i]);
    const tz = TZ_BY_LOC[c.locationId];
    (d as { contactId: string }).contactId = RECOVERED_CONTACTS[i];
    (d as { locationId: string }).locationId = c.locationId;
    (d as { tz: string }).tz = tz;
    (d as { startsAtUtc: string }).startsAtUtc = atLocalHour(5 + i, 11, tz, 0);
    (d as { bookedAtUtc: string }).bookedAtUtc = atLocalHour(-1, 12, tz, 0);
  });
}

// The last 4 booked drafts become reengagement bookings (source voice, agent reengagement).
const REENGAGE_APPT_DRAFTS = apptDrafts.filter((d) => d.status === 'booked').slice(-4);
const REENGAGE_APPT_IDS = REENGAGE_APPT_DRAFTS.map((d) => d.id);
REENGAGE_APPT_DRAFTS.forEach((d, i) => {
  (d as { source: AppointmentSource }).source = 'voice';
  d.originatingInteractionId = `call_ns_${pad(131 + i)}`;
});

// Assign originating booking interactions for non-reengagement completed/booked appts.
for (const d of apptDrafts) {
  if (d.originatingInteractionId) continue;
  if (d.status !== 'completed' && d.status !== 'booked') continue;
  if (d.source === 'voice' && voiceBookingCounter < VOICE_BOOKING_MAX) {
    voiceBookingCounter++;
    d.originatingInteractionId = `call_ns_${pad(voiceBookingCounter)}`;
  } else if ((d.source === 'whatsapp' || d.source === 'web_chat') && chatBookingCounter < CHAT_BOOKING_MAX) {
    chatBookingCounter++;
    d.originatingInteractionId = `chat_ns_${pad(chatBookingCounter)}`;
  }
}

// -- Booked-today and same-weekday-last-week cohorts (§4.1 booked card + WoW delta, D3) --
// Both cohorts are drawn from the *confirmed* bucket (whose future-start rows can legitimately
// be booked recently) so the *booked* bucket keeps its natural spread and continues to fill
// Jul 3–8 — otherwise those days go empty and the trailing-week denominator collapses.
// confirmed[0..8] are dated to last Thursday (same UTC weekday, 7 days back) for a plausible
// week-over-week delta; confirmed[9..19] are dated today. The first five today-cohort rows are
// booked before opening hours so §4.3's after-hours count stays >= 6 this month (D5) —
// afterHours per §6.1 is about when the booking was made, not the visit time.
const TODAY_COHORT = 10;
const LASTWEEK_COHORT = 10;
{
  const confirmedDrafts = apptDrafts.filter((d) => d.status === 'confirmed');
  confirmedDrafts.slice(0, LASTWEEK_COHORT).forEach((d, i) => {
    (d as { bookedAtUtc: string }).bookedAtUtc = atLocalHour(-7, 9 + (i % 4), d.tz, (i % 3) * 15);
  });
  confirmedDrafts.slice(LASTWEEK_COHORT, LASTWEEK_COHORT + TODAY_COHORT).forEach((d, i) => {
    if (i < 5) {
      (d as { afterHours: boolean }).afterHours = true;
      (d as { bookedAtUtc: string }).bookedAtUtc = atLocalHour(0, 7, d.tz, (i % 3) * 10); // before 08:00 open
    } else {
      (d as { afterHours: boolean }).afterHours = false;
      (d as { bookedAtUtc: string }).bookedAtUtc = atLocalHour(0, 9, d.tz, (i % 3) * 10); // business hours, < now
    }
  });
}

/* ==================================================================================
 * VOB records (§7, §8) — 45, every VobStatus, seeded aging rows, payer variance
 * ================================================================================== */

interface PayerProfile {
  readonly payer: string;
  readonly plan: string;
  readonly handleSeconds: number;
  readonly ivrSuccess: boolean;
}
const PAYER_PROFILE: Readonly<Record<string, PayerProfile>> = {
  Aetna: { payer: 'Aetna', plan: 'PPO Dental Plus', handleSeconds: 175, ivrSuccess: true },
  'Delta Dental': { payer: 'Delta Dental', plan: 'PPO Premier', handleSeconds: 150, ivrSuccess: true },
  BCBS: { payer: 'BCBS', plan: 'Blue Choice Dental', handleSeconds: 245, ivrSuccess: true },
  Cigna: { payer: 'Cigna', plan: 'Dental 1500', handleSeconds: 300, ivrSuccess: true },
  Humana: { payer: 'Humana', plan: 'Complete Dental', handleSeconds: 330, ivrSuccess: false },
  UnitedHealthcare: { payer: 'UnitedHealthcare', plan: 'Dental Core', handleSeconds: 420, ivrSuccess: false },
};

interface VobSpec {
  readonly payer: string;
  readonly status: VobStatus;
  readonly requestedHoursAgo: number;
  readonly linkAppt: boolean; // link to an upcoming appt (aging) or a completed appt
  readonly verifiedCallSeq?: number; // reserved call seq for the payer call
}

// Non-terminal aging rows: ≥3 red (>48h), ≥4 amber (24-48h), ≥2 fresh queued (<24h).
const AGING_VOB_SPECS: readonly VobSpec[] = [
  { payer: 'UnitedHealthcare', status: 'pending_callback', requestedHoursAgo: 60, linkAppt: true }, // red
  { payer: 'Humana', status: 'dialing', requestedHoursAgo: 52, linkAppt: true }, // red
  { payer: 'Cigna', status: 'on_call', requestedHoursAgo: 72, linkAppt: true }, // red
  { payer: 'BCBS', status: 'pending_callback', requestedHoursAgo: 50, linkAppt: true }, // red
  { payer: 'Aetna', status: 'queued', requestedHoursAgo: 30, linkAppt: true }, // amber
  { payer: 'Cigna', status: 'dialing', requestedHoursAgo: 28, linkAppt: true }, // amber
  { payer: 'BCBS', status: 'on_call', requestedHoursAgo: 40, linkAppt: true }, // amber
  { payer: 'Humana', status: 'pending_callback', requestedHoursAgo: 36, linkAppt: true }, // amber
  { payer: 'UnitedHealthcare', status: 'queued', requestedHoursAgo: 45, linkAppt: true }, // amber
  { payer: 'Delta Dental', status: 'queued', requestedHoursAgo: 2, linkAppt: true }, // fresh
  { payer: 'Aetna', status: 'queued', requestedHoursAgo: 6, linkAppt: true }, // fresh
  { payer: 'BCBS', status: 'queued', requestedHoursAgo: 10, linkAppt: true }, // fresh
];

// Terminal rows across payers with materially different verified rates & handle times.
function terminalSpecs(): VobSpec[] {
  const rows: { payer: string; status: VobStatus; verified: boolean }[] = [
    // Aetna — good payer: 6 verified, 1 partial
    ...Array(6).fill({ payer: 'Aetna', status: 'verified' as VobStatus }),
    { payer: 'Aetna', status: 'partial_coverage', verified: false },
    // Delta Dental — good: 5 verified, 1 needs_referral
    ...Array(5).fill({ payer: 'Delta Dental', status: 'verified' as VobStatus }),
    { payer: 'Delta Dental', status: 'needs_referral', verified: false },
    // BCBS — mixed
    ...Array(3).fill({ payer: 'BCBS', status: 'verified' as VobStatus }),
    { payer: 'BCBS', status: 'partial_coverage', verified: false },
    { payer: 'BCBS', status: 'needs_authorization', verified: false },
    { payer: 'BCBS', status: 'not_covered', verified: false },
    // Cigna — mixed, slower
    ...Array(2).fill({ payer: 'Cigna', status: 'verified' as VobStatus }),
    { payer: 'Cigna', status: 'needs_referral', verified: false },
    { payer: 'Cigna', status: 'needs_referral', verified: false },
    { payer: 'Cigna', status: 'partial_coverage', verified: false },
    // Humana — weak
    { payer: 'Humana', status: 'verified', verified: true },
    { payer: 'Humana', status: 'needs_authorization', verified: false },
    { payer: 'Humana', status: 'inactive_policy', verified: false },
    { payer: 'Humana', status: 'inactive_policy', verified: false },
    { payer: 'Humana', status: 'partial_coverage', verified: false },
    // UnitedHealthcare — problem payer: 0 verified
    { payer: 'UnitedHealthcare', status: 'unable_to_verify', verified: false },
    { payer: 'UnitedHealthcare', status: 'unable_to_verify', verified: false },
    { payer: 'UnitedHealthcare', status: 'member_not_found', verified: false },
    { payer: 'UnitedHealthcare', status: 'member_not_found', verified: false },
  ].map((r) => ({ payer: r.payer, status: r.status, verified: r.status === 'verified' }));

  let verifiedSeq = 31; // reserved call-seq block for VOB verified calls (31..47)
  return rows.map((r, i): VobSpec => ({
    payer: r.payer,
    status: r.status,
    // The first three terminal rows resolve within hours so their lastAttempt lands today,
    // keeping §4.2's "VOB completed today" card alive (D4); the rest are 3–33 days old.
    requestedHoursAgo: i < 3 ? 8 + i : 24 * (3 + (i % 30)),
    linkAppt: i % 3 !== 0, // most linked to a completed appt, some standalone
    verifiedCallSeq: r.verified ? verifiedSeq++ : undefined,
  }));
}

const ALL_VOB_SPECS: readonly VobSpec[] = [...AGING_VOB_SPECS, ...terminalSpecs()];

// Pools of appointment drafts to attach VOBs to.
const upcomingApptPool = apptDrafts
  .filter((d) => d.status === 'booked' || d.status === 'confirmed')
  .filter((d) => !REENGAGE_APPT_IDS.includes(d.id));
const completedApptPool = apptDrafts.filter((d) => d.status === 'completed');

let upcomingCursor = 0;
let completedCursor = 0;

const vobRecords: VobRecord[] = ALL_VOB_SPECS.map((spec, i): VobRecord => {
  const id = `v_ns_${pad(i + 1)}`;
  const profile = PAYER_PROFILE[spec.payer];
  const isTerminal = i >= AGING_VOB_SPECS.length;

  // Choose the appointment (aging rows -> upcoming; terminal -> completed) if linked.
  let apptDraft: ApptDraft | null = null;
  if (spec.linkAppt) {
    if (!isTerminal) {
      apptDraft = upcomingApptPool[upcomingCursor % upcomingApptPool.length];
      upcomingCursor++;
    } else {
      apptDraft = completedApptPool[completedCursor % completedApptPool.length];
      completedCursor++;
    }
  }
  const contactId = apptDraft ? apptDraft.contactId : contacts[(i * 5 + 11) % contacts.length].id;
  const locationId = apptDraft ? apptDraft.locationId : contactOf(contactId).locationId;

  if (apptDraft && apptDraft.vobId === null) {
    apptDraft.vobId = id;
  }
  const appointmentId = apptDraft && apptDraft.vobId === id ? apptDraft.id : null;

  const requestedAtUtc = hoursAgo(spec.requestedHoursAgo);
  const verified = spec.status === 'verified';
  const attemptCount = spec.status === 'queued' ? 0 : 1 + (i % 3);

  const attempts: VobAttempt[] = [];
  for (let a = 0; a < attemptCount; a++) {
    const at = hoursAgo(spec.requestedHoursAgo - a * 2 - 0.5);
    const isLast = a === attemptCount - 1;
    attempts.push({
      at,
      durationSeconds: profile.handleSeconds + (i % 5) * 12 - a * 20,
      outcome: isLast
        ? isTerminal
          ? spec.status
          : 'callback scheduled'
        : profile.ivrSuccess
          ? 'IVR navigated, reached rep'
          : 'IVR dead-end, retry',
      interactionId: isLast && spec.verifiedCallSeq ? `call_ns_${pad(spec.verifiedCallSeq)}` : null,
      payerReferenceNumber: profile.ivrSuccess || isTerminal ? `${spec.payer.slice(0, 3).toUpperCase()}-REF-${pad(70000 + i * 7 + a, 5)}` : null,
    });
  }

  const fullBenefits = {
    copayUsd: 40,
    deductibleUsd: 250,
    outOfPocketMaxUsd: 2000,
    coverageNotes: 'Diagnostic and preventive at 100%, basic at 80%, major at 50%.',
  };
  const partialBenefits = {
    copayUsd: 45,
    deductibleUsd: null,
    outOfPocketMaxUsd: null,
    coverageNotes: 'Copay confirmed; deductible and OOP max not returned by payer.',
  };
  const emptyBenefits = {
    copayUsd: null,
    deductibleUsd: null,
    outOfPocketMaxUsd: null,
    coverageNotes: null,
  };
  const benefits =
    verified
      ? fullBenefits
      : spec.status === 'partial_coverage' || spec.status === 'needs_authorization' || spec.status === 'needs_referral'
        ? partialBenefits
        : spec.status === 'not_covered'
          ? { ...emptyBenefits, coverageNotes: 'Service not a covered benefit under this plan.' }
          : emptyBenefits;

  const statusTimeline = [
    { at: requestedAtUtc, status: 'queued' as VobStatus, actor: 'system' },
    ...(attemptCount > 0
      ? [{ at: attempts[0].at, status: (isTerminal ? 'on_call' : spec.status) as VobStatus, actor: 'VOB Agent' }]
      : []),
    ...(isTerminal ? [{ at: attempts[attempts.length - 1].at, status: spec.status, actor: 'VOB Agent' }] : []),
  ];

  return {
    id,
    contactId,
    payer: profile.payer,
    plan: profile.plan,
    status: spec.status,
    appointmentId,
    assignedTo: i % 4 === 0 ? 'Dana Whitmore' : null,
    requestedAtUtc,
    lastAttemptAtUtc: attempts.length ? attempts[attempts.length - 1].at : null,
    attempts,
    benefits,
    priorAuthRequired: spec.status === 'needs_authorization' || i % 6 === 0,
    referralRequired: spec.status === 'needs_referral' || i % 8 === 0,
    ivrNavigationSucceeded: attemptCount > 0 ? profile.ivrSuccess : false,
    payerRepReached: attemptCount > 0 && profile.ivrSuccess,
    locationId,
    resolvedReason: verified ? 'verified_manually' : isTerminal && i % 5 === 0 ? 'other' : null,
    statusTimeline,
  };
});

const vobById = new Map(vobRecords.map((v) => [v.id, v]));

/* ==================================================================================
 * Appointment finalization — build typed Appointment objects with timelines etc.
 * ================================================================================== */

function agentForSource(src: AppointmentSource, isReengage: boolean): Appointment['bookedByAgent'] {
  if (isReengage) return 'reengagement';
  if (src === 'whatsapp' || src === 'web_chat') return 'chat';
  return 'receptionist';
}

function clampPast(ms: number): string {
  const cap = new Date(MOCK_NOW_UTC).getTime() - 3_600_000;
  return new Date(Math.min(ms, cap)).toISOString();
}

function confirmationAttemptsFor(status: AppointmentStatus, startsAtUtc: string): ConfirmationAttempt[] {
  const startMs = new Date(startsAtUtc).getTime();
  const at = (daysBeforeStart: number): string => clampPast(startMs - daysBeforeStart * 86_400_000);
  const mk = (daysBeforeStart: number, outcome: ConfirmationAttemptOutcome): ConfirmationAttempt => ({
    at: at(daysBeforeStart),
    outcome,
  });
  switch (status) {
    case 'confirmed':
    case 'completed':
      return [mk(2, 'voicemail'), mk(1, 'confirmed')];
    case 'no_show':
      return [mk(2, 'no_answer'), mk(1, 'voicemail')];
    case 'rescheduled':
      return [mk(2, 'reached'), mk(1, 'reschedule_requested')];
    case 'booked':
      return [];
    case 'cancelled':
      return [mk(3, 'reached')];
    default:
      return [];
  }
}

function timelineFor(d: ApptDraft): AppointmentTimelineEvent[] {
  const startMs = new Date(d.startsAtUtc).getTime();
  const agent = agentForSource(d.source, REENGAGE_APPT_IDS.includes(d.id));
  const events: AppointmentTimelineEvent[] = [{ at: d.bookedAtUtc, label: 'Booked', actor: agent }];
  const confSent = clampPast(startMs - 2 * 86_400_000);
  if (d.status !== 'booked' && d.status !== 'cancelled') {
    events.push({ at: confSent, label: 'Confirmation sent', actor: 'Verifier' });
  }
  if (d.status === 'confirmed' || d.status === 'completed') {
    events.push({ at: clampPast(startMs - 1 * 86_400_000), label: 'Confirmed', actor: 'Verifier' });
  }
  if (d.status === 'rescheduled') {
    events.push({ at: clampPast(startMs - 1 * 86_400_000), label: 'Rescheduled', actor: 'Verifier' });
  }
  if (d.status === 'completed') {
    events.push({ at: d.startsAtUtc, label: 'Completed', actor: 'Front desk — Dana' });
  }
  if (d.status === 'no_show') {
    events.push({ at: d.startsAtUtc, label: 'Marked no-show', actor: 'Front desk — Dana' });
  }
  if (d.status === 'cancelled') {
    events.push({ at: clampPast(startMs - 1.5 * 86_400_000), label: 'Cancelled', actor: 'Front desk — Priya' });
  }
  return events;
}

const appointments: Appointment[] = apptDrafts.map((d): Appointment => {
  const contact = contactOf(d.contactId);
  const isReengage = REENGAGE_APPT_IDS.includes(d.id);
  const hasVob = d.vobId !== null;
  const staffNotes =
    d.index % 5 === 0
      ? [
          {
            at: addMinutes(d.bookedAtUtc, 30),
            author: 'Front desk — Dana',
            body:
              d.triage === 'urgent'
                ? 'Patient reports severe pain; flagged for same-day triage review.'
                : 'Patient prefers morning slots; note for future scheduling.',
          },
        ]
      : [];

  return {
    id: d.id,
    contactId: d.contactId,
    startsAtUtc: d.startsAtUtc,
    serviceInterest: contact.serviceInterest,
    source: d.source,
    language: contact.language,
    insuranceCaptured: hasVob || (contact.insurance !== null && d.index % 3 !== 1),
    vobId: d.vobId,
    triage: d.triage,
    status: d.status,
    bookedByAgent: agentForSource(d.source, isReengage),
    bookedAtUtc: d.bookedAtUtc,
    locationId: d.locationId,
    afterHours: d.afterHours,
    originatingInteractionId: d.originatingInteractionId,
    timeline: timelineFor(d),
    confirmationAttempts: confirmationAttemptsFor(d.status, d.startsAtUtc),
    staffNotes,
  };
});

const apptById = new Map(appointments.map((a) => [a.id, a]));

/* ==================================================================================
 * Review requests (§13.1) — 8-stage funnel with drop-off, opt_out & declined
 * ================================================================================== */

interface ReviewSpec {
  readonly status: ReviewRequest['status'];
  readonly count: number;
  readonly hasCall: boolean;
}
const REVIEW_SPECS: readonly ReviewSpec[] = [
  { status: 'eligible', count: 4, hasCall: false },
  { status: 'called', count: 1, hasCall: true },
  { status: 'reached', count: 1, hasCall: true },
  { status: 'asked', count: 1, hasCall: true },
  { status: 'agreed', count: 1, hasCall: true },
  { status: 'link_sent', count: 2, hasCall: true },
  { status: 'posted', count: 6, hasCall: true },
  { status: 'declined', count: 2, hasCall: true },
  { status: 'opt_out', count: 1, hasCall: true },
];

const reviewEligibleAppts = appointments.filter((a) => a.status === 'completed');
const reviewRequests: ReviewRequest[] = [];
{
  let idx = 0;
  let reviewCallSeq = 101; // reserved review-call block (101..115)
  for (const spec of REVIEW_SPECS) {
    for (let k = 0; k < spec.count; k++) {
      const appt = reviewEligibleAppts[(idx * 3 + 5) % reviewEligibleAppts.length];
      const id = `rr_ns_${pad(idx + 1)}`;
      const interactionId = spec.hasCall ? `call_ns_${pad(reviewCallSeq++)}` : null;
      const calledAtUtc = spec.hasCall ? addMinutes(appt.startsAtUtc, 60 * 24) : null;
      const posted = spec.status === 'posted';
      reviewRequests.push({
        id,
        contactId: appt.contactId,
        appointmentId: appt.id,
        status: spec.status,
        calledAtUtc,
        callDurationSeconds: spec.hasCall ? 90 + (idx % 5) * 20 : null,
        linkClicked: posted || spec.status === 'link_sent' ? idx % 2 === 0 : false,
        postedRating: posted ? 4 + (idx % 2) : null,
        postedAtUtc: posted ? addMinutes(appt.startsAtUtc, 60 * 30 + idx * 120) : null,
        locationId: appt.locationId,
        interactionId,
      });
      idx++;
    }
  }
}

/* ==================================================================================
 * Campaigns (§14.2) — one per type; running / paused / completed
 * ================================================================================== */

const bookableForCampaign = appointments.filter((a) => a.status === 'completed' || a.status === 'booked');

function campaignContacts(
  prefix: string,
  bookedApptIds: readonly string[],
  extraContactBase: number,
): CampaignContact[] {
  const statuses: CampaignContact['status'][] = ['queued', 'attempted', 'reached', 'exhausted', 'opt_out'];
  const rows: CampaignContact[] = statuses.map((status, i): CampaignContact => {
    const contact = contacts[(extraContactBase + i * 4) % contacts.length];
    return {
      id: `${prefix}_cc_${pad(i + 1)}`,
      contactId: contact.id,
      status,
      attempts: status === 'queued' ? 0 : status === 'exhausted' ? 3 : 1 + (i % 2),
      lastOutcome:
        status === 'queued'
          ? null
          : status === 'reached'
            ? 'Spoke with patient, considering'
            : status === 'opt_out'
              ? 'Requested no further contact'
              : status === 'exhausted'
                ? 'Max attempts reached, no answer'
                : 'Left voicemail',
      bookedAppointmentId: null,
      optOut: status === 'opt_out',
    };
  });
  bookedApptIds.forEach((apptId, i) => {
    const appt = apptById.get(apptId)!;
    rows.push({
      id: `${prefix}_cc_${pad(statuses.length + i + 1)}`,
      contactId: appt.contactId,
      status: 'booked',
      attempts: 1 + (i % 2),
      lastOutcome: 'Booked appointment',
      bookedAppointmentId: apptId,
      optOut: false,
    });
  });
  return rows;
}

const campaigns: readonly Campaign[] = [
  {
    id: 'camp_ns_reengage',
    name: 'Lapsed Patient Winback',
    type: 'reengagement',
    status: 'running',
    audienceSize: 140,
    startedAtUtc: daysAgo(21),
    locationId: LOC_NORTH,
    audienceDefinition: ['No visit in the last 9 months', 'Has valid consent on file', 'Not on suppression list'],
    pacing: { callingWindowLocal: '09:00–18:00', maxAttempts: 3, retrySpacingHours: 48 },
    contacts: campaignContacts('reengage', REENGAGE_APPT_IDS, 1),
  },
  {
    id: 'camp_ns_noshow',
    name: 'No-Show Recovery — June',
    type: 'no_show_recovery',
    status: 'paused',
    audienceSize: 32,
    startedAtUtc: daysAgo(34),
    locationId: LOC_WEST,
    audienceDefinition: ['No-show in the last 30 days', 'No rebooked appointment yet'],
    pacing: { callingWindowLocal: '10:00–17:00', maxAttempts: 2, retrySpacingHours: 24 },
    contacts: campaignContacts('noshow', [bookableForCampaign[10].id], 8),
  },
  {
    id: 'camp_ns_recall',
    name: '6-Month Recall — Spring',
    type: 'recall',
    status: 'completed',
    audienceSize: 88,
    startedAtUtc: daysAgo(70),
    locationId: LOC_SOUTH,
    audienceDefinition: ['Last cleaning 6+ months ago', 'Active patient'],
    pacing: { callingWindowLocal: '09:00–16:00', maxAttempts: 3, retrySpacingHours: 72 },
    contacts: campaignContacts('recall', [bookableForCampaign[20].id, bookableForCampaign[24].id], 15),
  },
];

/* ==================================================================================
 * Optimization events (§12.4) — includes one full detected→verified cycle w/ +delta
 * ================================================================================== */

const optimizationEvents: readonly OptimizationEvent[] = [
  {
    // THE required full cycle: Receptionist closing sequence — visible grade lift.
    id: 'opt_ns_001',
    detectedAtUtc: daysAgo(27),
    agent: 'receptionist',
    status: 'verified',
    whatWasDetected: 'Calls ending without a proper closing detected across 14 calls',
    whatWasChanged: 'Closing sequence updated to confirm next steps and offer a callback window',
    gradeDelta: 11,
    deployedAtUtc: daysAgo(RECEPTIONIST_DEPLOY_DAYS_AGO),
    verifiedAtUtc: daysAgo(RECEPTIONIST_VERIFY_DAYS_AGO),
  },
  {
    id: 'opt_ns_002',
    detectedAtUtc: daysAgo(9),
    agent: 'vob',
    status: 'deployed',
    whatWasDetected: 'Longer-than-benchmark handle time on UnitedHealthcare IVR paths',
    whatWasChanged: 'IVR navigation path shortened for this payer',
    gradeDelta: null,
    deployedAtUtc: daysAgo(3),
    verifiedAtUtc: null,
  },
  {
    id: 'opt_ns_003',
    detectedAtUtc: daysAgo(5),
    agent: 'verifier',
    status: 'in_tuning',
    whatWasDetected: 'Reschedule requests not always captured on the first attempt',
    whatWasChanged: 'Reschedule capture prompt being refined',
    gradeDelta: null,
    deployedAtUtc: null,
    verifiedAtUtc: null,
  },
  {
    id: 'opt_ns_004',
    detectedAtUtc: daysAgo(2),
    agent: 'chat',
    status: 'detected',
    whatWasDetected: 'False containment on insurance questions detected across 8 web-chat sessions',
    whatWasChanged: 'Under review by Awaaz ops',
    gradeDelta: null,
    deployedAtUtc: null,
    verifiedAtUtc: null,
  },
  {
    id: 'opt_ns_005',
    detectedAtUtc: daysAgo(48),
    agent: 'review_taker',
    status: 'verified',
    whatWasDetected: 'Review ask delivered before confirming the visit went well',
    whatWasChanged: 'Ask reordered to follow a brief experience check',
    gradeDelta: 6,
    deployedAtUtc: daysAgo(40),
    verifiedAtUtc: daysAgo(30),
  },
  {
    id: 'opt_ns_006',
    detectedAtUtc: daysAgo(15),
    agent: 'reengagement',
    status: 'deployed',
    whatWasDetected: 'Opening too long, callers disengaging before the offer',
    whatWasChanged: 'Opening shortened; value offer moved earlier',
    gradeDelta: null,
    deployedAtUtc: daysAgo(8),
    verifiedAtUtc: null,
  },
  {
    id: 'opt_ns_007',
    detectedAtUtc: daysAgo(60),
    agent: 'receptionist',
    status: 'verified',
    whatWasDetected: 'Insurance capture skipped on shorter calls',
    whatWasChanged: 'Insurance capture step made non-skippable for new patients',
    gradeDelta: 4,
    deployedAtUtc: daysAgo(52),
    verifiedAtUtc: daysAgo(44),
  },
  {
    id: 'opt_ns_008',
    detectedAtUtc: daysAgo(4),
    agent: 'vob',
    status: 'in_tuning',
    whatWasDetected: 'Member-not-found responses not always retried with alternate lookup',
    whatWasChanged: 'Alternate member lookup being added to the flow',
    gradeDelta: null,
    deployedAtUtc: null,
    verifiedAtUtc: null,
  },
  {
    id: 'opt_ns_009',
    detectedAtUtc: daysAgo(1),
    agent: 'chat',
    status: 'detected',
    whatWasDetected: 'Slow first response during peak hours detected',
    whatWasChanged: 'Queued for Awaaz ops review',
    gradeDelta: null,
    deployedAtUtc: null,
    verifiedAtUtc: null,
  },
  {
    id: 'opt_ns_010',
    detectedAtUtc: daysAgo(35),
    agent: 'verifier',
    status: 'verified',
    whatWasDetected: 'Voicemail script too long, low callback rate',
    whatWasChanged: 'Voicemail shortened with a clear callback number',
    gradeDelta: 5,
    deployedAtUtc: daysAgo(28),
    verifiedAtUtc: daysAgo(22),
  },
];

/* ==================================================================================
 * Calls (§10.1) — 150, five voice agents (N1), all 10 dispositions, grade lift baked in
 * ================================================================================== */

function receptionistGrade(atUtc: string): number {
  const deployMs = new Date(daysAgo(RECEPTIONIST_DEPLOY_DAYS_AGO)).getTime();
  const before = new Date(atUtc).getTime() < deployMs;
  return before ? rng.int(78, 85) : rng.int(88, 95);
}

function buildTranscript(
  disposition: CallDisposition,
  agentLabel: string,
  firstName: string | null,
  atUtc: string,
  isTwoParty: boolean,
): InteractionMedia {
  const t = (offset: number, speaker: 'agent' | 'patient', text: string, redact: readonly RedactPhrase[] = []) =>
    turn(speaker, addSeconds(atUtc, offset), text, redact);
  const name = firstName ?? 'there';
  const nameRedact: RedactPhrase[] = firstName ? [{ phrase: firstName, kind: 'name' }] : [];
  const opening = isTwoParty
    ? `Thank you for calling Northside Dental. This call is recorded for quality. This is the ${agentLabel} line, how can I help?`
    : `Thank you for calling Northside Dental, this is the ${agentLabel} line, how can I help?`;

  const turns = [t(0, 'agent', opening)];
  switch (disposition) {
    case 'booked':
      turns.push(
        t(9, 'patient', `Hi, I'd like to book a cleaning. My name is ${name}.`, nameRedact),
        t(18, 'agent', `Happy to help, ${name}. I have Tuesday at 10am or Thursday at 2pm.`, nameRedact),
        t(28, 'patient', 'Thursday at 2 works.'),
        t(35, 'agent', "You're booked for Thursday at 2pm. Anything else before we wrap up?"),
      );
      break;
    case 'verified':
      turns.push(
        t(10, 'agent', 'Calling to verify eligibility for a patient with your office.'),
        t(20, 'patient', 'Member is active. Copay is forty dollars, deductible two fifty.'),
        t(30, 'agent', 'Confirming reference number for our records. Thank you.'),
      );
      break;
    case 'confirmed':
      turns.push(
        t(8, 'patient', `This is ${name}.`, nameRedact),
        t(14, 'agent', `Hi ${name}, confirming your appointment this week. Does that still work?`, nameRedact),
        t(22, 'patient', 'Yes, that works.'),
        t(27, 'agent', 'Great, you are confirmed. We will see you then.'),
      );
      break;
    case 'review_requested':
      turns.push(
        t(8, 'agent', `Hi ${name}, glad your visit went well. Would you be open to leaving us a quick review?`, nameRedact),
        t(18, 'patient', 'Sure, send me the link.'),
        t(24, 'agent', 'Sending it by text now. Thank you so much.'),
      );
      break;
    case 'reengaged_booked':
      turns.push(
        t(9, 'agent', `Hi ${name}, it has been a while since your last visit — would you like to come in for a checkup?`, nameRedact),
        t(20, 'patient', 'Actually yes, let us do next week.'),
        t(28, 'agent', 'Booked for next week. We look forward to seeing you.'),
      );
      break;
    case 'escalated':
      turns.push(
        t(8, 'patient', 'I have severe swelling and a lot of pain right now.'),
        t(16, 'agent', 'I understand. I am connecting you with our clinical staff right away.'),
        t(22, 'agent', 'Please hold while I transfer you to a team member.'),
      );
      break;
    case 'info_only':
    default:
      turns.push(
        t(8, 'patient', 'Just wanted to know your hours and if you take my insurance.'),
        t(16, 'agent', 'We are open Monday to Friday 8 to 5, Saturday 9 to 1, and we accept most major carriers.'),
        t(26, 'patient', 'Great, thank you.'),
      );
      break;
  }
  return {
    recordingUrl: `/recordings/${ORG_ID}/${disposition}-${Math.abs(new Date(atUtc).getTime() % 100000)}.mp3`,
    transcript: turns,
    consentDisclosureAtUtc: isTwoParty ? addSeconds(atUtc, 2) : null,
  };
}

interface CallSpec {
  readonly seq: number;
  readonly agent: CallInteraction['agent'];
  readonly direction: CallInteraction['direction'];
  readonly disposition: CallDisposition;
  readonly atUtc: string;
  readonly contactId: string | null;
  readonly locationId: string;
  readonly durationSeconds: number;
  readonly triage: TriageFlag;
  readonly firstAudioResponseMs: number;
  readonly linkedApptId?: string | null;
  readonly linkedVobId?: string | null;
  readonly linkedReviewRequestId?: string | null;
  readonly linkedCampaignId?: string | null;
}

const AGENT_LABEL: Readonly<Record<string, string>> = {
  receptionist: 'reception',
  vob: 'verification',
  verifier: 'confirmation',
  review_taker: 'review',
  reengagement: 'reengagement',
};

const callSpecs: CallSpec[] = [];

// -- Booking calls (receptionist, seq 1..15) -> the appt whose originating id points back.
{
  const bookingAppts = appointments.filter((a) => a.originatingInteractionId?.startsWith('call_ns_'));
  bookingAppts
    .filter((a) => Number(a.originatingInteractionId!.slice(-3)) <= VOICE_BOOKING_MAX)
    .forEach((appt) => {
      const seq = Number(appt.originatingInteractionId!.slice(-3));
      callSpecs.push({
        seq,
        agent: 'receptionist',
        direction: 'inbound',
        disposition: 'booked',
        atUtc: appt.bookedAtUtc,
        contactId: appt.contactId,
        locationId: appt.locationId,
        durationSeconds: 180 + (seq % 5) * 20,
        triage: appt.triage,
        firstAudioResponseMs: seq % 8 === 0 ? 910 : 500 + (seq % 6) * 40,
        linkedApptId: appt.id,
      });
    });
}

// -- VOB verified calls (seq 31..47) -> vob attempt references them.
vobRecords
  .filter((v) => v.status === 'verified')
  .forEach((v) => {
    const attempt = v.attempts.find((a) => a.interactionId);
    if (!attempt || !attempt.interactionId) return;
    const seq = Number(attempt.interactionId.slice(-3));
    callSpecs.push({
      seq,
      agent: 'vob',
      direction: 'outbound',
      disposition: 'verified',
      atUtc: attempt.at,
      contactId: v.contactId,
      locationId: v.locationId,
      durationSeconds: attempt.durationSeconds,
      triage: 'none',
      firstAudioResponseMs: 620 + (seq % 5) * 30,
      linkedVobId: v.id,
    });
  });

// -- Verifier confirmation calls (seq 51..75) -> relate to appts but do NOT create them (N2).
{
  const confirmAppts = appointments.filter((a) => a.status === 'confirmed').slice(0, 25);
  confirmAppts.forEach((appt, i) => {
    const seq = 51 + i;
    const disposition: CallDisposition = i % 6 === 5 ? 'no_answer' : i % 6 === 4 ? 'voicemail' : 'confirmed';
    callSpecs.push({
      seq,
      agent: 'verifier',
      direction: 'outbound',
      disposition,
      atUtc: minutesAgo(60 * 24 * (2 + (i % 6)) + i * 17),
      contactId: appt.contactId,
      locationId: appt.locationId,
      durationSeconds: disposition === 'confirmed' ? 60 + (i % 4) * 15 : 20,
      triage: 'none',
      firstAudioResponseMs: 480 + (i % 6) * 35,
    });
  });
}

// -- Review Taker calls (seq 101..115) -> review request references them.
reviewRequests
  .filter((r) => r.interactionId)
  .forEach((r) => {
    const seq = Number(r.interactionId!.slice(-3));
    const disposition: CallDisposition =
      r.status === 'called' ? 'no_answer' : 'review_requested';
    callSpecs.push({
      seq,
      agent: 'review_taker',
      direction: 'outbound',
      disposition,
      atUtc: r.calledAtUtc ?? daysAgo(10),
      contactId: r.contactId,
      locationId: r.locationId,
      durationSeconds: r.callDurationSeconds ?? 30,
      triage: 'none',
      firstAudioResponseMs: 520 + (seq % 5) * 30,
      linkedReviewRequestId: r.id,
    });
  });

// -- Reengagement calls (seq 131..145): 4 booked (link to appts+campaign), rest no-contact.
{
  REENGAGE_APPT_IDS.forEach((apptId, i) => {
    const appt = apptById.get(apptId)!;
    callSpecs.push({
      seq: 131 + i,
      agent: 'reengagement',
      direction: 'outbound',
      disposition: 'reengaged_booked',
      atUtc: appt.bookedAtUtc,
      contactId: appt.contactId,
      locationId: appt.locationId,
      durationSeconds: 150 + i * 15,
      triage: 'none',
      firstAudioResponseMs: 600 + i * 25,
      linkedApptId: appt.id,
      linkedCampaignId: 'camp_ns_reengage',
    });
  });
  const noContact: CallDisposition[] = ['no_answer', 'voicemail', 'no_answer', 'voicemail', 'abandoned', 'no_answer', 'voicemail', 'no_answer', 'voicemail', 'abandoned', 'no_answer'];
  noContact.forEach((disposition, i) => {
    const contact = contacts[(i * 6 + 2) % contacts.length];
    callSpecs.push({
      seq: 135 + i,
      agent: 'reengagement',
      direction: 'outbound',
      disposition,
      atUtc: daysAgo(2 + i),
      contactId: disposition === 'abandoned' ? null : contact.id,
      locationId: LOC_NORTH,
      durationSeconds: disposition === 'abandoned' ? 5 : 18,
      triage: 'none',
      firstAudioResponseMs: 700 + (i % 4) * 30,
      linkedCampaignId: 'camp_ns_reengage',
    });
  });
}

// -- Filler calls (seq 300+): receptionist info/escalated/no-answer/abandoned/vm, vob no-answers.
{
  let seq = 300;
  const escalatedContacts: string[] = [];
  const pushFiller = (
    agent: CallInteraction['agent'],
    disposition: CallDisposition,
    dayOffset: number,
    withContact: boolean,
    triage: TriageFlag,
    loc: string,
  ) => {
    const contact = withContact ? contacts[(seq * 3 + 7) % contacts.length] : null;
    callSpecs.push({
      seq: seq++,
      agent,
      direction: 'inbound',
      disposition,
      atUtc: minutesAgo(60 * 24 * dayOffset + (seq % 60) * 11),
      contactId: contact ? contact.id : null,
      locationId: loc,
      durationSeconds:
        disposition === 'abandoned'
          ? 4
          : disposition === 'no_answer'
            ? 0
            : disposition === 'voicemail'
              ? 22
              : 120 + (seq % 5) * 20,
      triage,
      firstAudioResponseMs: seq % 9 === 0 ? 880 + (seq % 5) * 30 : 460 + (seq % 7) * 35,
    });
    if (disposition === 'escalated' && contact) escalatedContacts.push(contact.id);
  };

  const locFor = (i: number) => LOC_CYCLE[i % LOC_CYCLE.length];
  // 26 info_only (receptionist), spread across time for the grade-lift chart
  for (let i = 0; i < 26; i++) pushFiller('receptionist', 'info_only', i % 45, true, i % 11 === 0 ? 'low' : 'none', locFor(i));
  // 12 escalated (receptionist) — escalation sources
  for (let i = 0; i < 12; i++)
    pushFiller('receptionist', 'escalated', 1 + (i % 20), true, i % 2 === 0 ? 'urgent' : 'high', i < 8 ? LOC_NORTH : locFor(i));
  // 8 no_answer, 6 abandoned, 5 voicemail (receptionist)
  for (let i = 0; i < 8; i++) pushFiller('receptionist', 'no_answer', 3 + i, false, 'none', locFor(i));
  for (let i = 0; i < 6; i++) pushFiller('receptionist', 'abandoned', 2 + i, false, 'none', locFor(i + 1));
  for (let i = 0; i < 5; i++) pushFiller('receptionist', 'voicemail', 4 + i, true, 'none', locFor(i + 2));
  // 4 vob no_answer, 2 vob voicemail
  for (let i = 0; i < 4; i++) pushFiller('vob', 'no_answer', 5 + i, true, 'none', locFor(i));
  for (let i = 0; i < 2; i++) pushFiller('vob', 'voicemail', 6 + i, true, 'none', locFor(i + 3));
}

// -- Inbound receptionist traffic (§4.1 booking-rate denominator, D1) --
// The booking rate is bookings / completed inbound interactions. With bookings spread and a
// large "booked today" cohort, the trailing windows would otherwise show a >100% rate. These
// info-only inbound calls raise the denominator so the rate lands in the ~60–80% healthcare
// FCR band (§6.1) in the today / week / month windows alike. Counts per UTC calendar day are
// tuned to the booking distribution; the block is dense today (a day of live inbound traffic)
// and light across the rest of the window where existing calls already cover the denominator.
{
  let seq = 400;
  // [dayOffset, count] — dayOffset 0 = today (Jul 9). Hours kept before MOCK_NOW on day 0.
  // Only days 0/3/5 fall in the trailing week and 0/3/5/8 in the month (they set those
  // denominators); the rest give the §12.2 30-day quality sparkline continuous graded
  // receptionist calls on both sides of the day-20 deployment so it reads as a real lift
  // rather than starting from an empty (zero) bucket.
  const TRAFFIC: readonly (readonly [number, number])[] = [
    [0, 14], [3, 2], [5, 2], [8, 2], [11, 2], [14, 2], [17, 2], [20, 2], [23, 2], [26, 2], [29, 2],
  ];
  for (const [dayOffset, count] of TRAFFIC) {
    for (let i = 0; i < count; i++) {
      const contact = contacts[(seq * 3 + 7) % contacts.length];
      const loc = LOC_CYCLE[seq % LOC_CYCLE.length];
      // On day 0 keep the call before the anchored now: 06:00–08:00 local is <= 14:00Z, safely
      // before 15:20Z in both America/Chicago and America/Denver.
      const atUtc =
        dayOffset === 0
          ? atLocalHour(0, 6 + (i % 3), TZ_BY_LOC[loc], (i % 5) * 10)
          : minutesAgo(60 * 24 * dayOffset + ((i * 37) % (60 * 8)));
      callSpecs.push({
        seq: seq++,
        agent: 'receptionist',
        direction: 'inbound',
        disposition: 'info_only',
        atUtc,
        contactId: contact.id,
        locationId: loc,
        durationSeconds: 95 + (i % 6) * 18,
        triage: 'none',
        firstAudioResponseMs: seq % 9 === 0 ? 870 : 470 + (i % 7) * 35,
      });
    }
  }

  /*
   * §2.6 — the custom agent must own real interactions.
   *
   * Without these, `/agents/post-op-followup` renders every KPI as an em-dash, and the
   * spec's "custom enterprise agents get a dashboard page with zero frontend work" is an
   * empty claim. `CallInteraction.agent` was widened to `InteractionAgentId` so a custom
   * agent can be attributed one at all.
   *
   * Its metrics contract declares `followups_placed`, `reached_rate`, and
   * `complications_flagged`. The generic derivation engine computes the first two from
   * these calls. It cannot compute the third from any field the fixture carries, so that
   * card renders `—` with a "not yet emitted" tooltip. That behaviour is left in place on
   * purpose: it shows a KPI an agent declares but does not emit degrading gracefully,
   * rather than displaying a fabricated number.
   */
  {
    const OUTCOMES: readonly (readonly [CallDisposition, number])[] = [
      ['info_only', 5],
      ['booked', 2],
      ['escalated', 1],
      ['voicemail', 3],
      ['no_answer', 2],
    ];
    let i = 0;
    for (const [disposition, count] of OUTCOMES) {
      for (let k = 0; k < count; k++) {
        const contact = contacts[(seq * 5 + 11) % contacts.length];
        const loc = LOC_CYCLE[seq % LOC_CYCLE.length];
        const dayOffset = 1 + ((i * 3) % 26);
        callSpecs.push({
          seq: seq++,
          agent: 'post_op_followup',
          direction: 'outbound',
          disposition,
          atUtc: minutesAgo(60 * 24 * dayOffset + ((i * 53) % (60 * 9))),
          contactId: contact.id,
          locationId: loc,
          durationSeconds: 70 + (i % 5) * 25,
          triage: disposition === 'escalated' ? 'high' : 'none',
          firstAudioResponseMs: 520 + (i % 6) * 40,
        });
        i += 1;
        void k;
      }
    }
  }

}

const NO_GRADE_DISPOSITIONS = new Set<CallDisposition>(['abandoned', 'no_answer', 'voicemail']);

const calls: CallInteraction[] = callSpecs
  .sort((a, b) => a.seq - b.seq)
  .map((s): CallInteraction => {
    const id = `call_ns_${pad(s.seq)}`;
    const graded = !NO_GRADE_DISPOSITIONS.has(s.disposition);
    const isTwoParty = s.locationId === LOC_NORTH;
    const firstName = s.contactId ? contactFirst(s.contactId) : null;

    let overall: number | null = null;
    if (graded) {
      if (s.agent === 'receptionist') overall = receptionistGrade(s.atUtc);
      else if (s.disposition === 'escalated') overall = rng.int(84, 92);
      else overall = rng.int(86, 96);
    }

    const media = graded
      ? buildTranscript(s.disposition, AGENT_LABEL[s.agent] ?? 'reception', firstName, s.atUtc, isTwoParty)
      : null;

    return {
      id,
      kind: 'call',
      atUtc: s.atUtc,
      direction: s.direction,
      agent: s.agent,
      contactId: s.contactId,
      durationSeconds: s.durationSeconds,
      disposition: s.disposition,
      triage: s.triage,
      grade: overall === null ? null : makeGrade(overall, rng),
      locationId: s.locationId,
      media,
      firstAudioResponseMs: s.firstAudioResponseMs,
      costUsd: Math.round((s.durationSeconds / 60) * 12) / 100 + 0.05,
      linked: {
        appointmentId: s.linkedApptId ?? null,
        vobId: s.linkedVobId ?? null,
        reviewRequestId: s.linkedReviewRequestId ?? null,
        campaignId: s.linkedCampaignId ?? null,
      },
    };
  });

const callById = new Map(calls.map((c) => [c.id, c]));

/* ==================================================================================
 * Chats (§9, §10.2) — 70, both channels, all 4 outcomes, handoff markers
 * ================================================================================== */

const CHAT_INTENTS: readonly string[] = [
  'booking',
  'pricing',
  'hours and directions',
  'insurance question',
  'clinical question routed',
  'other',
];

interface ChatSpec {
  readonly outcome: ChatInteraction['outcome'];
  readonly count: number;
}
const CHAT_SPECS: readonly ChatSpec[] = [
  { outcome: 'booked', count: 12 },
  { outcome: 'contained', count: 25 },
  { outcome: 'resolved', count: 20 },
  { outcome: 'escalated', count: 13 },
];

function chatMessages(
  outcome: ChatInteraction['outcome'],
  intent: string,
  firstName: string,
  startUtc: string,
): ChatMessage[] {
  const msgs: ChatMessage[] = [
    { at: startUtc, speaker: 'patient', text: `Hi, I have a question about ${intent}.`, isHandoffMarker: false },
    { at: addSeconds(startUtc, 20), speaker: 'agent', text: 'Happy to help! Could you share a bit more?', isHandoffMarker: false },
    { at: addSeconds(startUtc, 45), speaker: 'patient', text: 'Sure, here are the details.', isHandoffMarker: false },
  ];
  if (outcome === 'booked') {
    msgs.push({ at: addSeconds(startUtc, 70), speaker: 'agent', text: `You're booked, ${firstName}. Confirmation sent.`, isHandoffMarker: false });
  } else if (outcome === 'escalated') {
    msgs.push(
      { at: addSeconds(startUtc, 70), speaker: 'agent', text: 'This needs a team member — connecting you now.', isHandoffMarker: false },
      { at: addSeconds(startUtc, 95), speaker: 'human_staff', text: 'Hi, this is Dana from the front desk taking over.', isHandoffMarker: true },
    );
  } else {
    msgs.push({ at: addSeconds(startUtc, 70), speaker: 'agent', text: 'Anything else I can help with?', isHandoffMarker: false });
  }
  return msgs;
}

const chats: ChatInteraction[] = [];
{
  let idx = 0;
  // Chat-booked appts whose originating interaction is a chat (chat_ns_001..012).
  const chatBookedAppts = appointments
    .filter((a) => a.originatingInteractionId?.startsWith('chat_ns_'))
    .sort((a, b) => Number(a.originatingInteractionId!.slice(-3)) - Number(b.originatingInteractionId!.slice(-3)));

  for (const spec of CHAT_SPECS) {
    for (let k = 0; k < spec.count; k++) {
      const seq = idx + 1;
      const id = `chat_ns_${pad(seq)}`;
      const channel: ChatChannel = idx % 2 === 0 ? 'whatsapp' : 'web_chat';
      const contact = contacts[(idx * 5 + 4) % contacts.length];
      const intent = CHAT_INTENTS[idx % CHAT_INTENTS.length];
      const startUtc = minutesAgo(60 * 24 * (idx % 40) + idx * 13);
      const graded = spec.outcome !== 'escalated' ? rng.int(82, 96) : null;

      // Link booked chats to their appt (bidirectional with originatingInteractionId).
      let linkedApptId: string | null = null;
      if (spec.outcome === 'booked') {
        const appt = chatBookedAppts.find((a) => a.originatingInteractionId === id);
        if (appt) linkedApptId = appt.id;
      }

      chats.push({
        id,
        kind: 'chat',
        atUtc: startUtc,
        channel,
        contactId: contact.id,
        lastMessageAtUtc: addSeconds(startUtc, 120),
        outcome: spec.outcome,
        messageCount: spec.outcome === 'escalated' ? 5 : 4,
        intent: spec.outcome === 'booked' ? 'booking' : intent,
        language: contact.language,
        locationId: contact.locationId,
        responseLatencyMs: idx % 7 === 0 ? 950 : 380 + (idx % 6) * 60,
        grade: graded === null ? null : makeGrade(graded, rng),
        linked: { appointmentId: linkedApptId },
        messages: chatMessages(spec.outcome, intent, contact.identity?.firstName ?? 'there', startUtc),
      });
      idx++;
    }
  }
}
const chatById = new Map(chats.map((c) => [c.id, c]));

/* ==================================================================================
 * Escalations (§11) — 18, all 5 triggers, some open past threshold (banner), etc.
 * ================================================================================== */

const escalatedCalls = calls.filter((c) => c.disposition === 'escalated' && c.contactId);
const escalatedChats = chats.filter((c) => c.outcome === 'escalated');

interface EscSpec {
  readonly trigger: Escalation['trigger'];
  readonly status: Escalation['status'];
  readonly atMinutesAgo: number;
}
const ESC_SPECS: readonly EscSpec[] = [
  { trigger: 'triage_urgent_emergency', status: 'open', atMinutesAgo: 45 },
  { trigger: 'triage_urgent_emergency', status: 'open', atMinutesAgo: 120 },
  { trigger: 'triage_urgent_emergency', status: 'resolved', atMinutesAgo: 60 * 30 },
  { trigger: 'triage_high', status: 'open', atMinutesAgo: 60 * 6 },
  { trigger: 'triage_high', status: 'open', atMinutesAgo: 60 * 9 },
  { trigger: 'triage_high', status: 'acknowledged', atMinutesAgo: 60 * 20 },
  { trigger: 'triage_high', status: 'resolved', atMinutesAgo: 60 * 40 },
  { trigger: 'clinical_question', status: 'open', atMinutesAgo: 60 * 7 },
  { trigger: 'clinical_question', status: 'acknowledged', atMinutesAgo: 60 * 12 },
  { trigger: 'clinical_question', status: 'acknowledged', atMinutesAgo: 60 * 15 },
  { trigger: 'clinical_question', status: 'resolved', atMinutesAgo: 60 * 50 },
  { trigger: 'caller_requested_human', status: 'open', atMinutesAgo: 90 },
  { trigger: 'caller_requested_human', status: 'acknowledged', atMinutesAgo: 60 * 10 },
  { trigger: 'caller_requested_human', status: 'acknowledged', atMinutesAgo: 60 * 18 },
  { trigger: 'caller_requested_human', status: 'resolved', atMinutesAgo: 60 * 60 },
  { trigger: 'agent_initiated', status: 'open', atMinutesAgo: 60 * 8 },
  { trigger: 'agent_initiated', status: 'acknowledged', atMinutesAgo: 60 * 22 },
  { trigger: 'agent_initiated', status: 'resolved', atMinutesAgo: 60 * 70 },
];

const escalations: Escalation[] = ESC_SPECS.map((spec, i): Escalation => {
  // Sources: prefer escalated calls, then escalated chats.
  const useChat = i >= escalatedCalls.length;
  const source = useChat
    ? escalatedChats[(i - escalatedCalls.length) % escalatedChats.length]
    : escalatedCalls[i % escalatedCalls.length];
  const contactId = source.contactId!;
  const contact = contactOf(contactId);
  const atUtc = minutesAgo(spec.atMinutesAgo);
  const acknowledged = spec.status !== 'open';
  const routedTo =
    spec.trigger === 'triage_urgent_emergency' ? '+13125550188 (on-call)' : i % 2 === 0 ? 'Dr. Alvarez' : 'Dana Whitmore';
  return {
    id: `esc_ns_${pad(i + 1)}`,
    atUtc,
    contactId,
    sourceInteractionId: source.id,
    trigger: spec.trigger,
    routedTo,
    status: spec.status,
    acknowledgedAtUtc: acknowledged ? addMinutes(atUtc, 12) : null,
    acknowledgedBy: acknowledged ? (i % 2 === 0 ? 'Dana Whitmore' : 'Priya Nair') : null,
    resolutionNote:
      spec.status === 'resolved'
        ? spec.trigger === 'triage_urgent_emergency'
          ? 'Patient advised to seek same-day care; clinical staff followed up.'
          : 'Handled by staff; patient needs addressed and noted.'
        : null,
    locationId: contact.locationId,
  };
});

/* ==================================================================================
 * Flags (§12.5) — 8 across all 3 statuses, each pointing at a real interaction
 * ================================================================================== */

const gradedCalls = calls.filter((c) => c.grade !== null);
const flags: readonly FlaggedInteraction[] = [
  {
    id: 'flag_ns_001',
    interactionId: gradedCalls[2].id,
    submittedAtUtc: daysAgo(3),
    submittedBy: 'Dana Whitmore',
    status: 'submitted',
    reason: 'Agent quoted a price that seems out of date.',
    resolutionNote: null,
  },
  {
    id: 'flag_ns_002',
    interactionId: gradedCalls[7].id,
    submittedAtUtc: daysAgo(5),
    submittedBy: 'Priya Nair',
    status: 'submitted',
    reason: 'Closing felt abrupt; want a second look.',
    resolutionNote: null,
  },
  {
    id: 'flag_ns_003',
    interactionId: gradedCalls[11].id,
    submittedAtUtc: daysAgo(6),
    submittedBy: 'Dr. Alvarez',
    status: 'submitted',
    reason: 'Confirm the clinical boundary was respected.',
    resolutionNote: null,
  },
  {
    id: 'flag_ns_004',
    interactionId: gradedCalls[15].id,
    submittedAtUtc: daysAgo(9),
    submittedBy: 'Dana Whitmore',
    status: 'under_review',
    reason: 'Insurance capture was skipped on a new patient.',
    resolutionNote: null,
  },
  {
    id: 'flag_ns_005',
    interactionId: gradedCalls[19].id,
    submittedAtUtc: daysAgo(10),
    submittedBy: 'Priya Nair',
    status: 'under_review',
    reason: 'Long hold before agent responded.',
    resolutionNote: null,
  },
  {
    id: 'flag_ns_006',
    interactionId: chats.find((c) => c.grade !== null)!.id,
    submittedAtUtc: daysAgo(11),
    submittedBy: 'Dana Whitmore',
    status: 'under_review',
    reason: 'Chat answered an insurance question incorrectly.',
    resolutionNote: null,
  },
  {
    id: 'flag_ns_007',
    interactionId: gradedCalls[23].id,
    submittedAtUtc: daysAgo(16),
    submittedBy: 'Dr. Alvarez',
    status: 'resolved',
    reason: 'Verify escalation was routed correctly.',
    resolutionNote: 'Reviewed: routing was correct; used as a positive training example.',
  },
  {
    id: 'flag_ns_008',
    interactionId: gradedCalls[27].id,
    submittedAtUtc: daysAgo(22),
    submittedBy: 'Dana Whitmore',
    status: 'resolved',
    reason: 'Closing sequence missing.',
    resolutionNote: 'Confirmed and fed into the closing-sequence optimization (see timeline).',
  },
];

/* ==================================================================================
 * Private feedback & published reviews (§13.2)
 * ================================================================================== */

const reviewTakerCalls = calls.filter((c) => c.agent === 'review_taker' && c.disposition === 'review_requested');
const privateFeedback: readonly PrivateFeedback[] = [
  {
    id: 'pf_ns_001',
    atUtc: daysAgo(4),
    contactId: reviewTakerCalls[0].contactId!,
    summary: 'Felt the wait time was long at check-in.',
    sourceInteractionId: reviewTakerCalls[0].id,
    status: 'new',
    locationId: reviewTakerCalls[0].locationId,
  },
  {
    id: 'pf_ns_002',
    atUtc: daysAgo(8),
    contactId: reviewTakerCalls[1].contactId!,
    summary: 'Billing question was not fully resolved on the day.',
    sourceInteractionId: reviewTakerCalls[1].id,
    status: 'actioned',
    locationId: reviewTakerCalls[1].locationId,
  },
  {
    id: 'pf_ns_003',
    atUtc: daysAgo(13),
    contactId: reviewTakerCalls[2].contactId!,
    summary: 'Wanted more parking guidance before the visit.',
    sourceInteractionId: reviewTakerCalls[2].id,
    status: 'actioned',
    locationId: reviewTakerCalls[2].locationId,
  },
  {
    id: 'pf_ns_004',
    atUtc: daysAgo(19),
    contactId: reviewTakerCalls[3].contactId!,
    summary: 'Front desk was warm but the room felt cold.',
    sourceInteractionId: reviewTakerCalls[3].id,
    status: 'new',
    locationId: reviewTakerCalls[3].locationId,
  },
];

const REVIEW_EXCERPTS: readonly string[] = [
  'Friendly staff and easy scheduling.',
  'Dr. Alvarez explained everything clearly.',
  'Quick visit, no long wait.',
  'The reminder call was really helpful.',
  'Clean office and kind hygienist.',
  'They fit me in for an emergency same day.',
  'Great with my kids.',
  'Booking over WhatsApp was so convenient.',
];

const publishedReviews: readonly PublishedReview[] = Array.from({ length: 14 }, (_, i): PublishedReview => {
  const attributed = i < 8;
  const loc = LOC_CYCLE[i % LOC_CYCLE.length];
  return {
    id: `prev_ns_${pad(i + 1)}`,
    atUtc: daysAgo(2 + i * 4),
    rating: i % 7 === 0 ? 4 : 5,
    excerpt: REVIEW_EXCERPTS[i % REVIEW_EXCERPTS.length],
    url: `https://g.page/r/northside-dental/review/${pad(9000 + i, 4)}`,
    attributed,
    locationId: loc,
  };
});

/* ==================================================================================
 * Knowledge (§15), Members (§16.3), Lines (§16.5), Suppression, Invoices
 * ================================================================================== */

const knowledgeBlocks: readonly KnowledgeBlock[] = [
  {
    category: 'services_and_treatments',
    locationId: null,
    entries: [
      { label: 'Preventive', value: 'Exams, cleanings, sealants, fluoride' },
      { label: 'Restorative', value: 'Fillings, crowns, bridges, implants' },
      { label: 'Cosmetic', value: 'Whitening, veneers' },
      { label: 'Orthodontics', value: 'Braces and clear aligner consults' },
    ],
  },
  {
    category: 'pricing',
    locationId: null,
    entries: [
      { label: 'New patient exam', value: '$89 (waived with insurance)' },
      { label: 'Cleaning', value: '$120–$180' },
      { label: 'Whitening', value: 'From $299' },
    ],
  },
  {
    category: 'providers_and_schedules',
    locationId: LOC_NORTH,
    entries: [
      { label: 'Dr. Alvarez', value: 'Mon, Tue, Thu' },
      { label: 'Dr. Okafor', value: 'Wed, Fri' },
      { label: 'Hygiene team', value: 'Daily, 8am–4pm' },
    ],
  },
  {
    category: 'hours_and_holidays',
    locationId: null,
    entries: [
      { label: 'Weekdays', value: '8:00am–5:00pm' },
      { label: 'Saturday', value: '9:00am–1:00pm' },
      { label: 'Closed', value: 'Federal holidays' },
    ],
  },
  {
    category: 'insurance_carriers_accepted',
    locationId: null,
    entries: [
      { label: 'In-network', value: 'Aetna, BCBS, Cigna, Delta Dental' },
      { label: 'Out-of-network billing', value: 'UnitedHealthcare, Humana' },
    ],
  },
  {
    category: 'faq',
    locationId: null,
    entries: [
      { label: 'Do you take walk-ins?', value: 'Emergencies same-day when possible; call ahead.' },
      { label: 'Payment plans?', value: 'Yes, through CareCredit.' },
    ],
  },
  {
    category: 'booking_rules',
    locationId: null,
    entries: [
      { label: 'New patient buffer', value: '60 minutes' },
      { label: 'Returning patient buffer', value: '30 minutes' },
      { label: 'Cancellation window', value: '24 hours' },
    ],
  },
  {
    category: 'escalation_routing',
    locationId: null,
    entries: [
      { label: 'Urgent/Emergency', value: 'On-call clinician forwarding line' },
      { label: 'Clinical question', value: 'Route to clinical staff, never answered by agent' },
      { label: 'Caller requests human', value: 'Front desk queue' },
    ],
  },
];

const knowledgeRequests: readonly KnowledgeChangeRequest[] = [
  {
    id: 'kr_ns_001',
    category: 'pricing',
    proposedChange: 'Update whitening price to $329',
    reason: 'New supplier cost',
    requestedBy: 'Dana Whitmore',
    requestedAtUtc: daysAgo(1),
    status: 'requested',
    history: [{ at: daysAgo(1), status: 'requested' }],
  },
  {
    id: 'kr_ns_002',
    category: 'hours_and_holidays',
    proposedChange: 'Add extended Thursday hours to 7pm',
    reason: 'Evening demand',
    requestedBy: 'Priya Nair',
    requestedAtUtc: daysAgo(4),
    status: 'in_review',
    history: [
      { at: daysAgo(4), status: 'requested' },
      { at: daysAgo(3), status: 'in_review' },
    ],
  },
  {
    id: 'kr_ns_003',
    category: 'providers_and_schedules',
    proposedChange: 'Add Dr. Chen on Saturdays',
    reason: 'New associate',
    requestedBy: 'Dana Whitmore',
    requestedAtUtc: daysAgo(10),
    status: 'scheduled',
    history: [
      { at: daysAgo(10), status: 'requested' },
      { at: daysAgo(8), status: 'in_review' },
      { at: daysAgo(6), status: 'scheduled' },
    ],
  },
  {
    id: 'kr_ns_004',
    category: 'insurance_carriers_accepted',
    proposedChange: 'Mark UnitedHealthcare as out-of-network',
    reason: 'Contract lapsed',
    requestedBy: 'Owner',
    requestedAtUtc: daysAgo(18),
    status: 'live',
    history: [
      { at: daysAgo(18), status: 'requested' },
      { at: daysAgo(16), status: 'in_review' },
      { at: daysAgo(14), status: 'scheduled' },
      { at: daysAgo(12), status: 'live' },
    ],
  },
];

const members: readonly Member[] = [
  { id: 'm_ns_001', email: 'owner@northsidedental.example', name: 'Robert Northcliff', role: 'OWNER_ADMIN', lastActiveUtc: hoursAgo(2), mfaEnabled: true },
  { id: 'm_ns_002', email: 'dana@northsidedental.example', name: 'Dana Whitmore', role: 'MANAGER', lastActiveUtc: hoursAgo(1), mfaEnabled: true },
  { id: 'm_ns_003', email: 'priya@northsidedental.example', name: 'Priya Nair', role: 'MANAGER', lastActiveUtc: hoursAgo(5), mfaEnabled: false },
  { id: 'm_ns_004', email: 'frontdesk@northsidedental.example', name: 'Marcus Lee', role: 'VIEWER', lastActiveUtc: daysAgo(1), mfaEnabled: false },
  { id: 'm_ns_005', email: 'billing@northsidedental.example', name: 'Sofia Ramirez', role: 'VIEWER', lastActiveUtc: daysAgo(2), mfaEnabled: false },
];

const lines: readonly PhoneLine[] = [
  { id: 'ln_ns_001', number: fictionPhone(3001), kind: 'voice', locationId: LOC_NORTH, healthy: true, lastCheckedUtc: minutesAgo(8) },
  { id: 'ln_ns_002', number: fictionPhone(3002), kind: 'whatsapp', locationId: LOC_NORTH, healthy: true, lastCheckedUtc: minutesAgo(9) },
  { id: 'ln_ns_003', number: fictionPhone(3003), kind: 'voice', locationId: LOC_WEST, healthy: true, lastCheckedUtc: minutesAgo(11) },
  { id: 'ln_ns_004', number: fictionPhone(3004), kind: 'whatsapp', locationId: LOC_WEST, healthy: false, lastCheckedUtc: minutesAgo(14) },
  { id: 'ln_ns_005', number: fictionPhone(3005), kind: 'voice', locationId: LOC_SOUTH, healthy: true, lastCheckedUtc: minutesAgo(7) },
  { id: 'ln_ns_006', number: fictionPhone(3006), kind: 'whatsapp', locationId: LOC_SOUTH, healthy: true, lastCheckedUtc: minutesAgo(10) },
];

const SUPPRESSION_SPECS = [
  { source: 'patient_opt_out' as const, consent: 'Verbal opt-out on review call' },
  { source: 'patient_opt_out' as const, consent: 'Reengagement opt-out' },
  { source: 'patient_opt_out' as const, consent: 'SMS STOP received' },
  { source: 'patient_opt_out' as const, consent: null },
  { source: 'manual_add' as const, consent: 'Staff added at patient request' },
  { source: 'manual_add' as const, consent: 'Wrong number reported' },
  { source: 'manual_add' as const, consent: null },
  { source: 'manual_add' as const, consent: 'Duplicate contact merged' },
  { source: 'complaint' as const, consent: 'Complaint logged, do not contact' },
  { source: 'complaint' as const, consent: 'Escalated complaint' },
  { source: 'complaint' as const, consent: null },
  { source: 'complaint' as const, consent: 'Regulatory complaint noted' },
];
const suppressionList: readonly SuppressionEntry[] = SUPPRESSION_SPECS.map((s, i): SuppressionEntry => ({
  id: `sup_ns_${pad(i + 1)}`,
  phoneE164: fictionPhone(4001 + i),
  source: s.source,
  addedAtUtc: daysAgo(2 + i * 3),
  consentBasis: s.consent,
}));

const invoices: readonly Invoice[] = [
  { id: 'inv_ns_2026_07', periodLabel: 'July 2026', amountUsd: 2480, status: 'due', downloadUrl: `/invoices/${ORG_ID}/2026-07.pdf` },
  { id: 'inv_ns_2026_06', periodLabel: 'June 2026', amountUsd: 2410, status: 'paid', downloadUrl: `/invoices/${ORG_ID}/2026-06.pdf` },
  { id: 'inv_ns_2026_05', periodLabel: 'May 2026', amountUsd: 2295, status: 'paid', downloadUrl: `/invoices/${ORG_ID}/2026-05.pdf` },
  { id: 'inv_ns_2026_04', periodLabel: 'April 2026', amountUsd: 2360, status: 'paid', downloadUrl: `/invoices/${ORG_ID}/2026-04.pdf` },
  { id: 'inv_ns_2026_03', periodLabel: 'March 2026', amountUsd: 2180, status: 'paid', downloadUrl: `/invoices/${ORG_ID}/2026-03.pdf` },
  { id: 'inv_ns_2026_02', periodLabel: 'February 2026', amountUsd: 2090, status: 'paid', downloadUrl: `/invoices/${ORG_ID}/2026-02.pdf` },
];

/* ==================================================================================
 * Assembled fixture
 * ================================================================================== */

export const NORTHSIDE_FIXTURE: OrgFixture = {
  org: NORTHSIDE_DENTAL,
  contacts,
  appointments,
  vobRecords,
  calls,
  chats,
  escalations,
  optimizationEvents,
  flags,
  reviewRequests,
  privateFeedback,
  publishedReviews,
  campaigns,
  knowledgeBlocks,
  knowledgeRequests,
  members,
  lines,
  suppressionList,
  invoices,
  agents: AGENTS,
  // §16.4 / §4.6: 10,920 of 12,000 plan minutes = 91% → exercises the usage banner.
  liveCallsNow: 3,
  minutesConsumed: 10_920,
  chatSessionsConsumed: 2_600,
};

// Guard rails referenced by the audit script (kept internal, not exported as data).
export const __NORTHSIDE_INTERNAL = {
  apptById,
  vobById,
  callById,
  chatById,
  contactById,
  RECEPTIONIST_DEPLOY_DAYS_AGO,
  ageHours,
} as const;
