/**
 * MOCK DATA-ACCESS LAYER — the enforcement point for spec §2.1 (modes) and §2.2 (roles).
 *
 * FROZEN FILE (Foundation).
 *
 * §2.2: "Permission checks are server-side. The UI hides what the role cannot access;
 * the API independently rejects it."
 *
 * Guide Part A Rule 6: "Role and mode gating must be structurally real... i.e., a Viewer
 * role literally cannot render the fields the spec says a Viewer cannot see... the mock
 * data-access layer itself must refuse to return the gated fields for the wrong
 * role/mode, mirroring the spec's 'UI hides, API independently rejects' principle."
 *
 * Concretely, in this file:
 *   - A Viewer never receives a raw phone number. Not masked in CSS — absent from the
 *     returned object. There is nothing on the client to reveal.
 *   - NON-PHI mode never returns patient-level rows. The return type is a discriminated
 *     union, so a caller cannot even *type* a row access without first narrowing on
 *     `kind === 'rows'`.
 *   - Recordings and transcripts are omitted, not disabled.
 *
 * Every gated read that succeeds writes an audit event (§2.3).
 */

import { writeAuditEvent } from '@/shared/audit';
import type { DataMode, Role } from '@/shared/status-models';
import type {
  Appointment,
  CallInteraction,
  ChatInteraction,
  OrgFixture,
  PatientContact,
  VobRecord,
} from './schema';

/* ==================================================================================
 * Session
 * ================================================================================== */

export interface Session {
  readonly actor: string;
  readonly role: Role;
  readonly mode: DataMode;
  readonly orgId: string;
  /** §2.4 global location filter. `null` = all locations. */
  readonly locationId: string | null;
}

/* ==================================================================================
 * Capability predicates — derived from §2.1 and §2.2, in one place, never re-derived
 * ================================================================================== */

/** §2.1 "NON-PHI mode: ... No patient identity ... no patient-level rows." */
export function canSeePatientRows(s: Session): boolean {
  return s.mode === 'PHI_BAA';
}

/** §2.2 Viewer is not excluded from patient *names* — only from phone reveal. */
export function canSeePatientName(s: Session): boolean {
  return s.mode === 'PHI_BAA';
}

/** §2.2 "Viewer: ... no phone-number reveal". */
export function canRevealPhone(s: Session): boolean {
  return s.mode === 'PHI_BAA' && s.role !== 'VIEWER';
}

/** §2.2 "Viewer: ... no recordings, no transcripts". §2.1 NON-PHI: neither, for anyone. */
export function canAccessMedia(s: Session): boolean {
  return s.mode === 'PHI_BAA' && s.role !== 'VIEWER';
}

/** §2.2 "Viewer: ... no exports". §16.1 "role-gated to Owner and Manager". */
export function canExport(s: Session): boolean {
  return s.role !== 'VIEWER';
}

/** §16.2 "Audit Log (COMPLIANCE, PHI mode only, Owner only)". */
export function canSeeAuditLog(s: Session): boolean {
  return s.mode === 'PHI_BAA' && s.role === 'OWNER_ADMIN';
}

/** §2.2 "Manager: ... no Billing, no Members, no Audit Log". */
export function canSeeBilling(s: Session): boolean {
  return s.role === 'OWNER_ADMIN';
}

export function canSeeMembers(s: Session): boolean {
  return s.role === 'OWNER_ADMIN';
}

/** §16.5 "manual add and remove (audited, Owner and Manager)". */
export function canEditConsentList(s: Session): boolean {
  return s.role !== 'VIEWER';
}

/** §11.2 "Any Manager or Owner can acknowledge". */
export function canAcknowledgeEscalation(s: Session): boolean {
  return s.role !== 'VIEWER';
}

/** §8.3 row actions and §5.4 outcome controls are staff workflow, not Viewer surface. */
export function canPerformWorkflowActions(s: Session): boolean {
  return s.role !== 'VIEWER';
}

/** §14.2 "Pause and resume controls (Owner and Manager, audited)". */
export function canControlCampaigns(s: Session): boolean {
  return s.role !== 'VIEWER';
}

/* ==================================================================================
 * View types — what the UI is actually allowed to hold
 * ================================================================================== */

/**
 * The identity a caller receives. Note `phoneE164` is `null` for a Viewer: the raw value
 * never crosses the boundary, so `MaskedValue` has nothing to reveal and the reveal
 * control is not rendered. This is the difference between hiding and gating.
 */
export interface PatientIdentityView {
  readonly firstName: string;
  readonly lastName: string;
  /** §5.2 "masked as pattern". Always safe to render. */
  readonly phoneMasked: string;
  /** Present only when `canRevealPhone(session)`. */
  readonly phoneE164: string | null;
}

export type ContactView = Omit<PatientContact, 'identity'> & {
  readonly identity: PatientIdentityView | null;
};

export type AppointmentView = Appointment & {
  readonly contact: ContactView;
  readonly locationName?: string | null;
  readonly needsReview?: boolean;
  readonly hasScheduledTime?: boolean;
};
export type VobRecordView = VobRecord & {
  readonly contact: ContactView;
  readonly locationName?: string | null;
};
export type CallInteractionView = CallInteraction & {
  readonly contact: ContactView | null;
  readonly locationName?: string | null;
  /** Alternate callback number from Retell post-call extraction (masked). */
  readonly callbackNumberMasked?: string | null;
};
export type ChatInteractionView = ChatInteraction & { readonly contact: ContactView | null };

/**
 * §5.6 / §10.4: in NON-PHI mode these tabs "render aggregate counts only, table hidden".
 *
 * A discriminated union rather than an empty array, so a NON-PHI caller cannot silently
 * render an empty table and call it a degraded state. It must branch.
 */
export type GatedRows<T> =
  | { readonly kind: 'rows'; readonly rows: readonly T[] }
  | { readonly kind: 'aggregate'; readonly total: number; readonly reason: 'NON_PHI_MODE' };

/* ==================================================================================
 * Masking
 * ================================================================================== */

/**
 * §5.2 "Phone (masked as pattern, click-to-reveal, reveal audited)".
 * `+15551234567` -> `(•••) •••-4567`. The last four digits are the industry-standard
 * disambiguator front-desk staff use; nothing more is exposed.
 */
export function maskPhone(phoneE164: string): string {
  const digits = phoneE164.replace(/\D/g, '');
  const last4 = digits.slice(-4);
  return `(•••) •••-${last4}`;
}

/* ==================================================================================
 * Projection — the single choke point where gating happens
 * ================================================================================== */

function projectContact(contact: PatientContact, session: Session): ContactView {
  if (!contact.identity || !canSeePatientName(session)) {
    return { ...contact, identity: null };
  }

  return {
    ...contact,
    identity: {
      firstName: contact.identity.firstName,
      lastName: contact.identity.lastName,
      phoneMasked: maskPhone(contact.identity.phoneE164),
      // The raw number is withheld here, at the boundary — not later, in the component.
      phoneE164: canRevealPhone(session) ? contact.identity.phoneE164 : null,
    },
  };
}

function projectCall(call: CallInteraction, session: Session): CallInteraction {
  if (canAccessMedia(session)) return call;
  // Recording URL and transcript are removed from the payload entirely.
  return { ...call, media: null };
}

function projectChat(chat: ChatInteraction, session: Session): ChatInteraction {
  if (canAccessMedia(session)) return chat;
  return { ...chat, messages: null };
}

/** §2.4 "A global location filter sits in the top bar and persists across tabs." */
function inScope(locationId: string, session: Session): boolean {
  return session.locationId === null || session.locationId === locationId;
}

/* ==================================================================================
 * Readers
 * ================================================================================== */

function contactIndex(fixture: OrgFixture): ReadonlyMap<string, PatientContact> {
  return new Map(fixture.contacts.map((c) => [c.id, c]));
}

export function listAppointments(fixture: OrgFixture, session: Session): GatedRows<AppointmentView> {
  const scoped = fixture.appointments.filter((a) => inScope(a.locationId, session));

  if (!canSeePatientRows(session)) {
    return { kind: 'aggregate', total: scoped.length, reason: 'NON_PHI_MODE' };
  }

  const contacts = contactIndex(fixture);
  const rows = scoped.flatMap((appointment) => {
    const contact = contacts.get(appointment.contactId);
    if (!contact) return [];
    return [{ ...appointment, contact: projectContact(contact, session) }];
  });

  return { kind: 'rows', rows };
}

export function listVobRecords(fixture: OrgFixture, session: Session): GatedRows<VobRecordView> {
  const scoped = fixture.vobRecords.filter((v) => inScope(v.locationId, session));

  if (!canSeePatientRows(session)) {
    return { kind: 'aggregate', total: scoped.length, reason: 'NON_PHI_MODE' };
  }

  const contacts = contactIndex(fixture);
  const rows = scoped.flatMap((vob) => {
    const contact = contacts.get(vob.contactId);
    if (!contact) return [];
    return [{ ...vob, contact: projectContact(contact, session) }];
  });

  return { kind: 'rows', rows };
}

export function listCalls(fixture: OrgFixture, session: Session): GatedRows<CallInteractionView> {
  const scoped = fixture.calls.filter((c) => inScope(c.locationId, session));

  if (!canSeePatientRows(session)) {
    return { kind: 'aggregate', total: scoped.length, reason: 'NON_PHI_MODE' };
  }

  const contacts = contactIndex(fixture);
  const rows = scoped.map((call) => {
    const contact = call.contactId ? contacts.get(call.contactId) : undefined;
    return {
      ...projectCall(call, session),
      contact: contact ? projectContact(contact, session) : null,
    };
  });

  return { kind: 'rows', rows };
}

export function listChats(fixture: OrgFixture, session: Session): GatedRows<ChatInteractionView> {
  const scoped = fixture.chats.filter((c) => inScope(c.locationId, session));

  if (!canSeePatientRows(session)) {
    return { kind: 'aggregate', total: scoped.length, reason: 'NON_PHI_MODE' };
  }

  const contacts = contactIndex(fixture);
  const rows = scoped.map((chat) => {
    const contact = chat.contactId ? contacts.get(chat.contactId) : undefined;
    return {
      ...projectChat(chat, session),
      contact: contact ? projectContact(contact, session) : null,
    };
  });

  return { kind: 'rows', rows };
}

/* ==================================================================================
 * Audited actions — §2.3
 *
 * These are the *only* sanctioned way to obtain a raw phone number, play a recording,
 * read a transcript, search, or export. Each refuses first and audits second, so a denied
 * attempt never produces a misleading "success" audit row.
 * ================================================================================== */

export class PermissionDeniedError extends Error {
  constructor(action: string, role: Role, mode: DataMode) {
    super(`Permission denied: ${action} is not available to ${role} in ${mode} mode.`);
    this.name = 'PermissionDeniedError';
  }
}

/** §5.2 "click-to-reveal, reveal audited". Returns the raw number or throws. */
export function revealPhone(identity: PatientIdentityView, session: Session, objectRef: string): string {
  if (!canRevealPhone(session) || identity.phoneE164 === null) {
    throw new PermissionDeniedError('phone number reveal', session.role, session.mode);
  }

  writeAuditEvent({
    actor: session.actor,
    role: session.role,
    eventType: 'phone_number_reveal',
    objectRef,
    locationId: session.locationId,
  });

  return identity.phoneE164;
}

/** §10.1 "Audio player for the recording (role-gated, playback audited)". */
export function playRecording(session: Session, interactionId: string): void {
  if (!canAccessMedia(session)) {
    throw new PermissionDeniedError('recording playback', session.role, session.mode);
  }
  writeAuditEvent({
    actor: session.actor,
    role: session.role,
    eventType: 'recording_playback',
    objectRef: `interaction:${interactionId}`,
    locationId: session.locationId,
  });
}

/** §2.3 "transcript view" is an audited event in its own right. */
export function viewTranscript(session: Session, interactionId: string): void {
  if (!canAccessMedia(session)) {
    throw new PermissionDeniedError('transcript view', session.role, session.mode);
  }
  writeAuditEvent({
    actor: session.actor,
    role: session.role,
    eventType: 'transcript_view',
    objectRef: `interaction:${interactionId}`,
    locationId: session.locationId,
  });
}

/** §5.3 "free-text search on name and phone (search is audited in PHI mode)". */
export function recordPatientSearch(session: Session, query: string): void {
  if (session.mode !== 'PHI_BAA') return; // §5.3 scopes the audit to PHI mode explicitly.
  if (query.trim() === '') return;

  writeAuditEvent({
    actor: session.actor,
    role: session.role,
    eventType: 'patient_search',
    objectRef: 'search:appointments',
    locationId: session.locationId,
    // The query itself is a PHI-bearing string; record that a search happened and how
    // broad it was, never what was typed.
    detail: { queryLength: String(query.trim().length) },
  });
}

/**
 * §16.1 "every export audited with row-count and filter parameters recorded".
 * The audit row is written before the file is produced, so an export that fails midway
 * still leaves a trace that it was attempted with those parameters.
 */
export function recordExport(
  session: Session,
  table: string,
  rowCount: number,
  filters: Readonly<Record<string, string>>,
): void {
  if (!canExport(session)) {
    throw new PermissionDeniedError('export', session.role, session.mode);
  }
  writeAuditEvent({
    actor: session.actor,
    role: session.role,
    eventType: 'export',
    objectRef: `table:${table}`,
    locationId: session.locationId,
    detail: { rowCount: String(rowCount), ...filters },
  });
}

/** §5.4 "Staff notes (append-only, audited)". */
export function recordNoteEdit(session: Session, objectRef: string): void {
  if (!canPerformWorkflowActions(session)) {
    throw new PermissionDeniedError('note edit', session.role, session.mode);
  }
  writeAuditEvent({
    actor: session.actor,
    role: session.role,
    eventType: 'note_edit',
    objectRef,
    locationId: session.locationId,
  });
}

/** §5.4 "manual buttons for Completed and No-show". */
export function recordAppointmentStatusChange(
  session: Session,
  appointmentId: string,
  from: string,
  to: string,
): void {
  if (!canPerformWorkflowActions(session)) {
    throw new PermissionDeniedError('appointment status change', session.role, session.mode);
  }
  writeAuditEvent({
    actor: session.actor,
    role: session.role,
    eventType: 'appointment_status_change',
    objectRef: `appointment:${appointmentId}`,
    locationId: session.locationId,
    detail: { from, to },
  });
}

/** §8.3 "Every action writes an audit event and updates the status timeline." */
export function recordVobQueueAction(
  session: Session,
  vobId: string,
  action: string,
  detail: Readonly<Record<string, string>> = {},
): void {
  if (!canPerformWorkflowActions(session)) {
    throw new PermissionDeniedError('VOB queue action', session.role, session.mode);
  }
  writeAuditEvent({
    actor: session.actor,
    role: session.role,
    eventType: 'vob_queue_action',
    objectRef: `vob:${vobId}`,
    locationId: session.locationId,
    detail: { action, ...detail },
  });
}

/** §15.2 change-request workflow. */
export function recordKnowledgeChangeRequest(session: Session, category: string): void {
  writeAuditEvent({
    actor: session.actor,
    role: session.role,
    eventType: 'knowledge_change_request',
    objectRef: `knowledge:${category}`,
    locationId: session.locationId,
  });
}

/** §16.5 "manual add and remove (audited, Owner and Manager)". */
export function recordConsentListChange(session: Session, phoneMasked: string, action: 'add' | 'remove'): void {
  if (!canEditConsentList(session)) {
    throw new PermissionDeniedError('consent list change', session.role, session.mode);
  }
  writeAuditEvent({
    actor: session.actor,
    role: session.role,
    eventType: 'consent_list_change',
    objectRef: `suppression:${phoneMasked}`,
    locationId: session.locationId,
    detail: { action },
  });
}

/** §16.3 "Role changes audited." */
export function recordPermissionChange(session: Session, memberId: string, from: Role, to: Role): void {
  if (!canSeeMembers(session)) {
    throw new PermissionDeniedError('permission change', session.role, session.mode);
  }
  writeAuditEvent({
    actor: session.actor,
    role: session.role,
    eventType: 'permission_change',
    objectRef: `member:${memberId}`,
    locationId: session.locationId,
    detail: { from, to },
  });
}
