/**
 * CEDAR FAMILY CLINIC — the deliberately sparse fixture.
 *
 * Its whole job is to prove the degraded / empty render paths the spec requires:
 *  - §2.4  single location → the location filter must hide
 *  - §4.3  `avgAppointmentValueUsd: null` → the revenue card hides
 *  - §4.1  `outcomeDataAvailable: false` → the no-show card hides (never a misleading zero)
 *  - §5.6  `appointments: []` → the "No appointments yet" empty state renders
 *  - §11 / §14  `escalations: []` and `campaigns: []` → those empty states render
 *
 * A handful of calls, chats, and VOB records exist so the agent tabs are not blank. With
 * no appointments, every VOB `appointmentId` and every call/chat `linked.appointmentId`
 * is `null`, and `reviewRequests` (which require an appointment) is empty.
 */

import { CEDAR_FAMILY } from '@/mock/orgs';
import type {
  AgentRegistryEntry,
  CallInteraction,
  ChatInteraction,
  Invoice,
  KnowledgeBlock,
  Member,
  OrgFixture,
  PatientContact,
  PhoneLine,
  SuppressionEntry,
  VobRecord,
} from '@/mock/schema';
import type { AgentId, CallDirection, CallDisposition, Language } from '@/shared/status-models';
import { addSeconds, daysAgo, fictionPhone, hoursAgo, makeGrade, makePrng, minutesAgo, pad, turn } from './helpers';

const ORG_ID = CEDAR_FAMILY.id;
const LOC = 'loc_cedar';
const rng = makePrng(0x0ceda201);

/* Standard agent registry only — no custom agent for the sparse org. */
const AGENTS: readonly AgentRegistryEntry[] = [
  {
    id: 'receptionist',
    name: 'Receptionist',
    type: 'inbound',
    channel: 'voice',
    icon: 'Headset',
    isCustom: false,
    slug: 'receptionist',
    metricsContract: [{ key: 'bookings', label: 'Appointments booked', format: 'count' }],
  },
  {
    id: 'vob',
    name: 'VOB Agent',
    type: 'outbound',
    channel: 'voice',
    icon: 'ShieldCheck',
    isCustom: false,
    slug: 'vob-agent',
    metricsContract: [{ key: 'verifications', label: 'Verifications', format: 'count' }],
  },
  {
    id: 'verifier',
    name: 'Verifier',
    type: 'outbound',
    channel: 'voice',
    icon: 'CalendarDays',
    isCustom: false,
    slug: 'verifier',
    metricsContract: [{ key: 'confirmation_attempts', label: 'Confirmation attempts', format: 'count' }],
  },
  {
    id: 'chat',
    name: 'Chat Agents',
    type: 'inbound',
    channel: 'chat',
    icon: 'MessageSquare',
    isCustom: false,
    slug: 'chat-agents',
    metricsContract: [{ key: 'sessions', label: 'Sessions', format: 'count' }],
  },
  {
    id: 'review_taker',
    name: 'Review Taker',
    type: 'outbound',
    channel: 'voice',
    icon: 'Star',
    isCustom: false,
    slug: 'review-taker',
    metricsContract: [{ key: 'reviews_posted', label: 'Reviews posted', format: 'count' }],
  },
  {
    id: 'reengagement',
    name: 'Reengagement',
    type: 'outbound',
    channel: 'voice',
    icon: 'PhoneOutgoing',
    isCustom: false,
    slug: 'reengagement',
    metricsContract: [{ key: 'bookings', label: 'Bookings generated', format: 'count' }],
  },
];

/* A small contact pool. */
const CEDAR_NAMES: readonly { first: string; last: string; lang: Language }[] = [
  { first: 'Harold', last: 'Kim', lang: 'en' },
  { first: 'Beatriz', last: 'Salas', lang: 'es' },
  { first: 'George', last: 'Whitaker', lang: 'en' },
  { first: 'Ingrid', last: 'Larsen', lang: 'other' },
  { first: 'Patricia', last: 'Nolan', lang: 'en' },
  { first: 'Rafael', last: 'Duarte', lang: 'es' },
  { first: 'Susan', last: 'Meyer', lang: 'en' },
  { first: 'Omar', last: 'Haddad', lang: 'other' },
];

const contacts: readonly PatientContact[] = CEDAR_NAMES.map((n, i): PatientContact => ({
  id: `c_cd_${pad(i + 1)}`,
  identity: { firstName: n.first, lastName: n.last, phoneE164: fictionPhone(6000 + i) },
  insurance:
    i % 3 === 0
      ? null
      : { carrier: 'Aetna', plan: 'PPO Dental Plus', memberIdMasked: `••••${pad(5100 + i, 4)}`, groupNumber: null },
  serviceInterest: ['New patient exam', 'Cleaning', 'Filling', 'Crown'][i % 4],
  language: n.lang,
  locationId: LOC,
  consentBasis: 'Existing patient relationship',
  suppressed: i === 7,
}));

/* A few VOB records — appointmentId null (there are no appointments). */
const vobRecords: readonly VobRecord[] = [
  {
    id: 'v_cd_001',
    contactId: 'c_cd_002',
    payer: 'Aetna',
    plan: 'PPO Dental Plus',
    status: 'verified',
    appointmentId: null,
    assignedTo: null,
    requestedAtUtc: daysAgo(3),
    lastAttemptAtUtc: daysAgo(3),
    attempts: [
      { at: daysAgo(3), durationSeconds: 165, outcome: 'verified', interactionId: 'call_cd_002', payerReferenceNumber: 'AET-REF-51001' },
    ],
    benefits: { copayUsd: 35, deductibleUsd: 200, outOfPocketMaxUsd: 1800, coverageNotes: 'Preventive at 100%.' },
    priorAuthRequired: false,
    referralRequired: false,
    ivrNavigationSucceeded: true,
    payerRepReached: true,
    locationId: LOC,
    resolvedReason: 'verified_manually',
    statusTimeline: [
      { at: daysAgo(3), status: 'queued', actor: 'system' },
      { at: daysAgo(3), status: 'verified', actor: 'VOB Agent' },
    ],
  },
  {
    id: 'v_cd_002',
    contactId: 'c_cd_005',
    payer: 'Cigna',
    plan: 'Dental 1500',
    status: 'pending_callback',
    appointmentId: null,
    assignedTo: 'Cedar front desk',
    requestedAtUtc: hoursAgo(30),
    lastAttemptAtUtc: hoursAgo(28),
    attempts: [
      { at: hoursAgo(28), durationSeconds: 310, outcome: 'callback scheduled', interactionId: null, payerReferenceNumber: 'CIG-REF-51002' },
    ],
    benefits: { copayUsd: null, deductibleUsd: null, outOfPocketMaxUsd: null, coverageNotes: null },
    priorAuthRequired: false,
    referralRequired: false,
    ivrNavigationSucceeded: true,
    payerRepReached: false,
    locationId: LOC,
    resolvedReason: null,
    statusTimeline: [
      { at: hoursAgo(30), status: 'queued', actor: 'system' },
      { at: hoursAgo(28), status: 'pending_callback', actor: 'VOB Agent' },
    ],
  },
  {
    id: 'v_cd_003',
    contactId: 'c_cd_006',
    payer: 'UnitedHealthcare',
    plan: 'Dental Core',
    status: 'unable_to_verify',
    appointmentId: null,
    assignedTo: null,
    requestedAtUtc: daysAgo(6),
    lastAttemptAtUtc: daysAgo(5),
    attempts: [
      { at: daysAgo(5), durationSeconds: 420, outcome: 'unable_to_verify', interactionId: null, payerReferenceNumber: null },
    ],
    benefits: { copayUsd: null, deductibleUsd: null, outOfPocketMaxUsd: null, coverageNotes: null },
    priorAuthRequired: false,
    referralRequired: false,
    ivrNavigationSucceeded: false,
    payerRepReached: false,
    locationId: LOC,
    resolvedReason: null,
    statusTimeline: [
      { at: daysAgo(6), status: 'queued', actor: 'system' },
      { at: daysAgo(5), status: 'unable_to_verify', actor: 'VOB Agent' },
    ],
  },
];

/* A handful of calls. linked.appointmentId is null (no appointments exist). */
interface CedarCallSpec {
  readonly seq: number;
  readonly agent: AgentId;
  readonly disp: CallDisposition;
  readonly dir: CallDirection;
  readonly contactId: string | null;
  readonly dur: number;
  readonly grade: number | null;
  readonly vobId: string | null;
}
const CEDAR_CALL_SPECS: readonly CedarCallSpec[] = [
  { seq: 1, agent: 'receptionist', disp: 'info_only', dir: 'inbound', contactId: 'c_cd_001', dur: 140, grade: 90, vobId: null },
  { seq: 2, agent: 'vob', disp: 'verified', dir: 'outbound', contactId: 'c_cd_002', dur: 165, grade: 92, vobId: 'v_cd_001' },
  { seq: 3, agent: 'receptionist', disp: 'info_only', dir: 'inbound', contactId: 'c_cd_003', dur: 95, grade: 88, vobId: null },
  { seq: 4, agent: 'receptionist', disp: 'no_answer', dir: 'inbound', contactId: null, dur: 0, grade: null, vobId: null },
  { seq: 5, agent: 'verifier', disp: 'voicemail', dir: 'outbound', contactId: 'c_cd_004', dur: 20, grade: null, vobId: null },
  { seq: 6, agent: 'review_taker', disp: 'review_requested', dir: 'outbound', contactId: 'c_cd_005', dur: 85, grade: 91, vobId: null },
];
const calls: readonly CallInteraction[] = CEDAR_CALL_SPECS.map((c): CallInteraction => {
  const id = `call_cd_${pad(c.seq)}`;
  const atUtc = minutesAgo(60 * 24 * (c.seq % 7) + c.seq * 23);
  const graded = c.grade !== null;
  const firstName = c.contactId ? CEDAR_NAMES[Number(c.contactId.slice(-3)) - 1]?.first ?? 'there' : 'there';
  return {
    id,
    kind: 'call',
    atUtc,
    direction: c.dir,
    agent: c.agent,
    contactId: c.contactId,
    durationSeconds: c.dur,
    disposition: c.disp,
    triage: 'none',
    grade: graded ? makeGrade(c.grade!, rng) : null,
    locationId: LOC,
    // Cedar's single location is one-party consent → no disclosure event.
    media: graded
      ? {
          recordingUrl: `/recordings/${ORG_ID}/${c.disp}-${c.seq}.mp3`,
          transcript: [
            turn('agent', atUtc, 'Thank you for calling Cedar Family Clinic, how can I help?'),
            turn('patient', addSeconds(atUtc, 10), `Hi, this is ${firstName}.`, [{ phrase: firstName, kind: 'name' }]),
            turn('agent', addSeconds(atUtc, 20), 'Happy to help with that.'),
          ],
          consentDisclosureAtUtc: null,
        }
      : null,
    firstAudioResponseMs: c.seq % 4 === 0 ? 840 : 520 + c.seq * 20,
    costUsd: Math.round((c.dur / 60) * 12) / 100 + 0.05,
    linked: { appointmentId: null, vobId: c.vobId, reviewRequestId: null, campaignId: null },
  };
});

/* A few chats. linked.appointmentId null. */
const chats: readonly ChatInteraction[] = [
  { seq: 1, channel: 'web_chat' as const, outcome: 'contained' as const, contactId: 'c_cd_001', intent: 'hours and directions', grade: 89 },
  { seq: 2, channel: 'whatsapp' as const, outcome: 'resolved' as const, contactId: 'c_cd_003', intent: 'pricing', grade: 90 },
  { seq: 3, channel: 'web_chat' as const, outcome: 'contained' as const, contactId: 'c_cd_007', intent: 'insurance question', grade: 87 },
  { seq: 4, channel: 'whatsapp' as const, outcome: 'escalated' as const, contactId: 'c_cd_006', intent: 'clinical question routed', grade: null },
].map((c): ChatInteraction => {
  const id = `chat_cd_${pad(c.seq)}`;
  const atUtc = minutesAgo(60 * 24 * (c.seq % 5) + c.seq * 31);
  const contact = contacts.find((x) => x.id === c.contactId)!;
  return {
    id,
    kind: 'chat',
    atUtc,
    channel: c.channel,
    contactId: c.contactId,
    lastMessageAtUtc: addSeconds(atUtc, 90),
    outcome: c.outcome,
    messageCount: c.outcome === 'escalated' ? 5 : 4,
    intent: c.intent,
    language: contact.language,
    locationId: LOC,
    responseLatencyMs: 420 + c.seq * 40,
    grade: c.grade === null ? null : makeGrade(c.grade, rng),
    linked: { appointmentId: null },
    messages: [
      { at: atUtc, speaker: 'patient', text: `Hi, question about ${c.intent}.`, isHandoffMarker: false },
      { at: addSeconds(atUtc, 20), speaker: 'agent', text: 'Happy to help!', isHandoffMarker: false },
      ...(c.outcome === 'escalated'
        ? [{ at: addSeconds(atUtc, 60), speaker: 'human_staff' as const, text: 'Front desk taking over now.', isHandoffMarker: true }]
        : [{ at: addSeconds(atUtc, 60), speaker: 'agent' as const, text: 'Anything else?', isHandoffMarker: false }]),
    ],
  };
});

const knowledgeBlocks: readonly KnowledgeBlock[] = [
  {
    category: 'hours_and_holidays',
    locationId: null,
    entries: [
      { label: 'Weekdays', value: '8:00am–5:00pm' },
      { label: 'Saturday', value: '9:00am–1:00pm' },
    ],
  },
  {
    category: 'services_and_treatments',
    locationId: null,
    entries: [{ label: 'General', value: 'Exams, cleanings, fillings' }],
  },
  {
    category: 'insurance_carriers_accepted',
    locationId: null,
    entries: [{ label: 'In-network', value: 'Aetna, Cigna' }],
  },
];

const members: readonly Member[] = [
  { id: 'm_cd_001', email: 'owner@cedarfamily.example', name: 'Lauren Cedar', role: 'OWNER_ADMIN', lastActiveUtc: hoursAgo(3), mfaEnabled: true },
  { id: 'm_cd_002', email: 'desk@cedarfamily.example', name: 'Tom Reyes', role: 'MANAGER', lastActiveUtc: daysAgo(1), mfaEnabled: false },
];

const lines: readonly PhoneLine[] = [
  { id: 'ln_cd_001', number: fictionPhone(6501), kind: 'voice', locationId: LOC, healthy: true, lastCheckedUtc: minutesAgo(12) },
  { id: 'ln_cd_002', number: fictionPhone(6502), kind: 'whatsapp', locationId: LOC, healthy: true, lastCheckedUtc: minutesAgo(15) },
];

const suppressionList: readonly SuppressionEntry[] = [
  { id: 'sup_cd_001', phoneE164: fictionPhone(6701), source: 'patient_opt_out', addedAtUtc: daysAgo(5), consentBasis: 'SMS STOP received' },
  { id: 'sup_cd_002', phoneE164: fictionPhone(6702), source: 'manual_add', addedAtUtc: daysAgo(12), consentBasis: null },
];

const invoices: readonly Invoice[] = [
  { id: 'inv_cd_2026_07', periodLabel: 'July 2026', amountUsd: 620, status: 'due', downloadUrl: `/invoices/${ORG_ID}/2026-07.pdf` },
  { id: 'inv_cd_2026_06', periodLabel: 'June 2026', amountUsd: 590, status: 'paid', downloadUrl: `/invoices/${ORG_ID}/2026-06.pdf` },
];

export const CEDAR_FIXTURE: OrgFixture = {
  org: CEDAR_FAMILY,
  contacts,
  appointments: [], // §5.6 empty state
  vobRecords,
  calls,
  chats,
  escalations: [], // §11 empty state
  optimizationEvents: [],
  flags: [],
  reviewRequests: [], // require an appointment, of which there are none
  privateFeedback: [],
  publishedReviews: [],
  campaigns: [], // §14 empty state
  knowledgeBlocks,
  knowledgeRequests: [],
  members,
  lines,
  suppressionList,
  invoices,
  agents: AGENTS,
  liveCallsNow: 0,
  minutesConsumed: 610,
  chatSessionsConsumed: 40,
};
