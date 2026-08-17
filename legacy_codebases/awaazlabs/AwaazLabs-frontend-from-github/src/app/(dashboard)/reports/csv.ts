/**
 * §16.1 on-demand CSV builders for the operational tables (Appointments, VOB Queue,
 * Conversations, Campaigns contacts).
 *
 * SECURITY — the one rule that governs this whole file:
 * Every builder reads ONLY from the *projected* views the data-access layer returns
 * (`AppointmentView`, `VobRecordView`, `CallInteractionView`, `ChatInteractionView`, and a
 * `ContactView` map). The raw E.164 phone field is never referenced here. A phone the user
 * has not revealed exports as its mask — exactly the value the table renders — and a Viewer (who
 * cannot export at all; `recordExport` throws) never reaches a builder. Follows the
 * `vob-queue/vob-export.ts` pattern.
 */

import { formatDateTime, formatDuration, timezoneFor } from '@/lib/format';
import { getLocationById } from '@/mock/orgs';
import type {
  AppointmentView,
  CallInteractionView,
  ChatInteractionView,
  ContactView,
  VobRecordView,
} from '@/mock/data-access';
import type { Campaign, CampaignContact } from '@/mock/schema';
import {
  AGENT_LABELS,
  APPOINTMENT_SOURCE_LABELS,
  APPOINTMENT_STATUS_LABELS,
  CALL_DISPOSITION_LABELS,
  CAMPAIGN_CONTACT_STATUS_LABELS,
  TRIAGE_FLAG_LABELS,
  VOB_STATUS_LABELS,
} from '@/shared/status-models';

/** RFC-4180 field escaping: wrap in quotes and double any embedded quote. */
function csvField(value: string): string {
  if (/[",\r\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function toCsv(columns: readonly string[], rows: ReadonlyArray<readonly string[]>): string {
  const header = columns.map(csvField).join(',');
  const body = rows.map((r) => r.map(csvField).join(','));
  return [header, ...body].join('\r\n');
}

/** A phone is only ever the projected mask — never the raw number. */
function phoneOf(contact: ContactView | null): string {
  return contact?.identity?.phoneMasked ?? '—';
}

function nameOf(contact: ContactView | null): string {
  const id = contact?.identity;
  return id ? `${id.firstName} ${id.lastName}` : 'Unknown patient';
}

/** Triggers a client-side Blob download. No network, no server round-trip. */
export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/* ==================================================================================
 * Builders — each takes rows already projected by the data-access layer.
 * ================================================================================== */

const APPOINTMENT_COLUMNS = [
  'Patient name',
  'Phone (masked)',
  'Service interest',
  'Status',
  'Source',
  'Triage',
  'Booked by',
  'Booked at',
  'Appointment time',
  'Insurance captured',
  'Location',
] as const;

export function buildAppointmentsCsv(rows: readonly AppointmentView[], orgId: string): string {
  const body = rows.map((a) => {
    const tz = timezoneFor(orgId, a.locationId);
    return [
      nameOf(a.contact),
      phoneOf(a.contact),
      a.serviceInterest,
      APPOINTMENT_STATUS_LABELS[a.status],
      APPOINTMENT_SOURCE_LABELS[a.source],
      TRIAGE_FLAG_LABELS[a.triage],
      AGENT_LABELS[a.bookedByAgent],
      formatDateTime(a.bookedAtUtc, tz),
      formatDateTime(a.startsAtUtc, tz),
      a.insuranceCaptured ? 'Yes' : 'No',
      a.locationId,
    ];
  });
  return toCsv(APPOINTMENT_COLUMNS, body);
}

const VOB_COLUMNS = [
  'Patient name',
  'Phone (masked)',
  'Payer',
  'Plan',
  'Status',
  'Assigned to',
  'Requested at',
  'Last attempt',
  'Attempts',
  'Location',
] as const;

export function buildVobCsv(rows: readonly VobRecordView[], orgId: string): string {
  const body = rows.map((v) => {
    const tz = timezoneFor(orgId, v.locationId);
    return [
      nameOf(v.contact),
      phoneOf(v.contact),
      v.payer,
      v.plan,
      VOB_STATUS_LABELS[v.status],
      v.assignedTo ?? '',
      formatDateTime(v.requestedAtUtc, tz),
      v.lastAttemptAtUtc ? formatDateTime(v.lastAttemptAtUtc, tz) : '—',
      String(v.attempts.length),
      v.locationName ?? getLocationById(orgId, v.locationId)?.name ?? v.locationId,
    ];
  });
  return toCsv(VOB_COLUMNS, body);
}

const CONVERSATION_COLUMNS = [
  'Timestamp',
  'Type',
  'Channel',
  'Direction',
  'Patient name',
  'Phone (masked)',
  'Outcome',
  'Duration',
  'Messages',
  'Agent / intent',
  'Grade',
  'Location',
] as const;

const CHANNEL_LABELS: Readonly<Record<string, string>> = {
  whatsapp: 'WhatsApp',
  web_chat: 'Web Chat',
};

/**
 * §10 Conversations spans calls and chats. The two record shapes are unified into one
 * interaction table so a single CSV mirrors the tab. Fields that do not apply to a kind are
 * left blank rather than faked.
 */
export function buildConversationsCsv(
  calls: readonly CallInteractionView[],
  chats: readonly ChatInteractionView[],
  orgId: string,
): string {
  const callRows = calls.map((c) => {
    const tz = timezoneFor(orgId, c.locationId);
    return [
      formatDateTime(c.atUtc, tz),
      'Call',
      'Voice',
      c.direction,
      nameOf(c.contact),
      phoneOf(c.contact),
      CALL_DISPOSITION_LABELS[c.disposition],
      formatDuration(c.durationSeconds),
      '',
      AGENT_LABELS[c.agent],
      c.grade ? String(c.grade.overall) : '',
      c.locationId,
    ];
  });

  const chatRows = chats.map((c) => {
    const tz = timezoneFor(orgId, c.locationId);
    return [
      formatDateTime(c.atUtc, tz),
      'Chat',
      CHANNEL_LABELS[c.channel] ?? c.channel,
      '',
      nameOf(c.contact),
      phoneOf(c.contact),
      c.outcome,
      '',
      String(c.messageCount),
      c.intent,
      c.grade ? String(c.grade.overall) : '',
      c.locationId,
    ];
  });

  // Newest first, matching the tab's default ordering.
  const merged = [...callRows, ...chatRows].sort((a, b) =>
    a[0] < b[0] ? 1 : a[0] > b[0] ? -1 : 0,
  );
  return toCsv(CONVERSATION_COLUMNS, merged);
}

export function buildCallsCsv(calls: readonly CallInteractionView[], orgId: string): string {
  return buildConversationsCsv(calls, [], orgId);
}

export function buildChatsCsv(chats: readonly ChatInteractionView[], orgId: string): string {
  return buildConversationsCsv([], chats, orgId);
}

const ESCALATION_COLUMNS = [
  'Patient name',
  'Trigger',
  'Status',
  'Routed to',
  'Acknowledged at',
  'Acknowledged by',
  'Created at',
  'Location',
] as const;

export interface EscalationCsvRow {
  readonly patientName: string;
  readonly triggerLabel: string;
  readonly statusLabel: string;
  readonly routedTo: string;
  readonly acknowledgedAt: string;
  readonly acknowledgedBy: string;
  readonly createdAt: string;
  readonly locationName: string;
}

export function buildEscalationsCsv(rows: readonly EscalationCsvRow[]): string {
  const body = rows.map((row) => [
    row.patientName,
    row.triggerLabel,
    row.statusLabel,
    row.routedTo,
    row.acknowledgedAt,
    row.acknowledgedBy,
    row.createdAt,
    row.locationName,
  ]);
  return toCsv(ESCALATION_COLUMNS, body);
}

const CAMPAIGN_CONTACT_COLUMNS = [
  'Campaign',
  'Campaign type',
  'Patient name',
  'Phone (masked)',
  'Contact status',
  'Attempts',
  'Last outcome',
  'Booked appointment',
  'Opt-out',
  'Location',
] as const;

export interface CampaignContactRow {
  readonly campaign: Campaign;
  readonly contact: CampaignContact;
  /** Projected identity view for this contact, or null when not surfaced by any reader. */
  readonly contactView: ContactView | null;
}

export function buildCampaignContactsCsv(rows: readonly CampaignContactRow[]): string {
  const body = rows.map(({ campaign, contact, contactView }) => [
    campaign.name,
    campaign.type,
    nameOf(contactView),
    phoneOf(contactView),
    CAMPAIGN_CONTACT_STATUS_LABELS[contact.status],
    String(contact.attempts),
    contact.lastOutcome ?? '',
    contact.bookedAppointmentId ?? '',
    contact.optOut ? 'Yes' : 'No',
    campaign.locationId,
  ]);
  return toCsv(CAMPAIGN_CONTACT_COLUMNS, body);
}
