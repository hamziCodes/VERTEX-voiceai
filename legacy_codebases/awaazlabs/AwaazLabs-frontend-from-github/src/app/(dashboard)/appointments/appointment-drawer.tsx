'use client';

/**
 * §5.4 Appointment detail drawer (slide-over). All eight sub-items:
 *  1. Full appointment record with unmask-on-demand fields
 *  2. Originating interaction link → /conversations/calls?interaction={id}
 *  3. VOB card when a verification exists
 *  4. Confirmation and reminder history (each Verifier attempt with outcome)
 *  5. Timeline (booked, confirmation sent, confirmed/rescheduled, outcome; timestamped + actor)
 *  6. Outcome control (manual Completed / No-show), gated on canPerformWorkflowActions
 *  7. Staff notes (append-only, audited)
 *  8. Flag this interaction (routes to Qualicall priority review, §12.5)
 *
 * Built on the Drawer primitive (Radix Dialog: focus trap, Escape, ARIA). Drawer state is
 * local to the parent client.
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { ExternalLink, Flag } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Drawer } from '@/components/ui/drawer';
import { MaskedValue } from '@/components/ui/masked-value';
import { AppointmentStatusChip, TriageChip, VobStatusChip } from '@/components/ui/status-chip';
import { formatDateTime, formatUsd, timezoneFor } from '@/lib/format';
import { getLocationById } from '@/mock/orgs';
import { canPerformWorkflowActions, type AppointmentView, type Session } from '@/mock/data-access';
import type { VobRecord } from '@/mock/schema';
import {
  AGENT_LABELS,
  APPOINTMENT_SOURCE_LABELS,
  APPOINTMENT_STATUS_LABELS,
  CONFIRMATION_ATTEMPT_OUTCOME_LABELS,
  LANGUAGE_LABELS,
  type AppointmentStatus,
} from '@/shared/status-models';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border py-4 first:border-t-0 first:pt-0">
      <h3 className="mb-3 text-sm font-semibold text-foreground">{title}</h3>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm text-foreground">{children}</dd>
    </div>
  );
}

function usd(value: number | null): string {
  return value === null ? '—' : formatUsd(value);
}

export function AppointmentDrawer({
  appointment,
  vobRecord,
  session,
  flagged,
  onStatusChange,
  onAddNote,
  onFlag,
  onClose,
}: {
  appointment: AppointmentView;
  vobRecord: VobRecord | null;
  session: Session;
  flagged: boolean;
  onStatusChange: (to: AppointmentStatus) => void;
  onAddNote: (body: string) => void;
  onFlag: () => void;
  onClose: () => void;
}) {
  const [noteDraft, setNoteDraft] = useState('');

  const tz = timezoneFor(session.orgId, appointment.locationId);
  const identity = appointment.contact.identity;
  const name = identity ? `${identity.firstName} ${identity.lastName}` : 'Appointment';
  const locationName = appointment.locationName ?? getLocationById(session.orgId, appointment.locationId)?.name ?? appointment.locationId;
  const canAct = canPerformWorkflowActions(session);
  const isTerminal =
    appointment.status === 'completed' ||
    appointment.status === 'cancelled' ||
    appointment.status === 'no_show';

  const submitNote = () => {
    const body = noteDraft.trim();
    if (body === '') return;
    onAddNote(body);
    setNoteDraft('');
  };

  return (
    <Drawer
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={name}
      description={`${appointment.serviceInterest} · ${APPOINTMENT_STATUS_LABELS[appointment.status]}`}
    >
      {/* 1. Full appointment record with unmask-on-demand fields */}
      <Section title="Appointment record">
        <dl className="grid grid-cols-2 gap-4">
          <Field label="Date and time">{formatDateTime(appointment.startsAtUtc, tz)}</Field>
          <Field label="Status">
            <AppointmentStatusChip status={appointment.status} />
          </Field>
          <Field label="Patient">{name}</Field>
          <Field label="Phone">
            {identity ? (
              <MaskedValue identity={identity} session={session} objectRef={`appointment:${appointment.id}`} />
            ) : (
              '—'
            )}
          </Field>
          <Field label="Treatment or service interest">{appointment.serviceInterest}</Field>
          <Field label="Source">{APPOINTMENT_SOURCE_LABELS[appointment.source]}</Field>
          <Field label="Language">{LANGUAGE_LABELS[appointment.language]}</Field>
          <Field label="Insurance captured">
            <Badge variant={appointment.insuranceCaptured ? 'outline' : 'secondary'}>
              {appointment.insuranceCaptured ? 'Yes' : 'No'}
            </Badge>
          </Field>
          <Field label="Triage">
            <TriageChip status={appointment.triage} />
          </Field>
          <Field label="Booked by">
            {AGENT_LABELS[appointment.bookedByAgent]} · {formatDateTime(appointment.bookedAtUtc, tz)}
          </Field>
          <Field label="Location">{locationName}</Field>
        </dl>
      </Section>

      {/* 2. Originating interaction link */}
      <Section title="Originating interaction">
        {appointment.originatingInteractionId ? (
          <Link
            href={`/conversations/calls?interaction=${appointment.originatingInteractionId}`}
            className="inline-flex items-center gap-1.5 text-sm text-foreground hover:underline"
          >
            <ExternalLink className="h-4 w-4" aria-hidden="true" />
            Open call or chat with recording, transcript, and QA grade
          </Link>
        ) : (
          <p className="text-sm text-muted-foreground">No originating interaction is linked to this appointment.</p>
        )}
      </Section>

      {/* 3. VOB card when a verification exists */}
      {vobRecord ? (
        <Section title="Insurance verification (VOB)">
          <dl className="grid grid-cols-2 gap-4">
            <Field label="Payer">{vobRecord.payer}</Field>
            <Field label="Coverage status">
              <VobStatusChip status={vobRecord.status} />
            </Field>
            <Field label="Copay">{usd(vobRecord.benefits.copayUsd)}</Field>
            <Field label="Deductible">{usd(vobRecord.benefits.deductibleUsd)}</Field>
            <Field label="Out-of-pocket max">{usd(vobRecord.benefits.outOfPocketMaxUsd)}</Field>
            <Field label="Prior authorization">{vobRecord.priorAuthRequired ? 'Required' : 'Not required'}</Field>
            <Field label="Last updated">
              {formatDateTime(vobRecord.lastAttemptAtUtc ?? vobRecord.requestedAtUtc, tz)}
            </Field>
          </dl>
          <Link href="/vob-queue" className="mt-3 inline-flex items-center gap-1.5 text-sm text-foreground hover:underline">
            <ExternalLink className="h-4 w-4" aria-hidden="true" />
            Open the VOB queue record
          </Link>
        </Section>
      ) : null}

      {/* 4. Confirmation and reminder history */}
      <Section title="Confirmation and reminder history">
        {appointment.confirmationAttempts.length === 0 ? (
          <p className="text-sm text-muted-foreground">No confirmation attempts recorded.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {appointment.confirmationAttempts.map((attempt, i) => (
              <li key={`${attempt.at}-${i}`} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-muted-foreground">{formatDateTime(attempt.at, tz)}</span>
                <Badge variant="secondary">{CONFIRMATION_ATTEMPT_OUTCOME_LABELS[attempt.outcome]}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* 5. Timeline */}
      <Section title="Timeline">
        <ol className="flex flex-col gap-3">
          {appointment.timeline.map((event, i) => (
            <li key={`${event.at}-${i}`} className="flex flex-col gap-0.5 border-l-2 border-border pl-3">
              <span className="text-sm font-medium text-foreground">{event.label}</span>
              <span className="text-xs text-muted-foreground">
                {formatDateTime(event.at, tz)} · {event.actor}
              </span>
            </li>
          ))}
        </ol>
      </Section>

      {/* 6. Outcome control */}
      <Section title="Outcome">
        {canAct ? (
          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={isTerminal}
                onClick={() => onStatusChange('completed')}
              >
                Mark completed
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={isTerminal}
                onClick={() => onStatusChange('no_show')}
              >
                Mark no-show
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Manual outcome entry for clinics without calendar write-back. Feeds no-show analytics.
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Outcome actions require Manager or Owner access.</p>
        )}
      </Section>

      {/* 7. Staff notes (append-only, audited) */}
      <Section title="Staff notes">
        {appointment.staffNotes.length === 0 ? (
          <p className="text-sm text-muted-foreground">No staff notes yet.</p>
        ) : (
          <ul className="mb-3 flex flex-col gap-3">
            {appointment.staffNotes.map((note, i) => (
              <li key={`${note.at}-${i}`} className="rounded-md border border-border p-3 text-sm">
                <p className="text-foreground">{note.body}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {note.author} · {formatDateTime(note.at, tz)}
                </p>
              </li>
            ))}
          </ul>
        )}
        {canAct ? (
          <div className="flex flex-col gap-2">
            <label htmlFor="staff-note" className="sr-only">
              Add a staff note
            </label>
            <textarea
              id="staff-note"
              value={noteDraft}
              onChange={(e) => setNoteDraft(e.target.value)}
              rows={3}
              placeholder="Add an append-only note…"
              className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <div>
              <Button size="sm" disabled={noteDraft.trim() === ''} onClick={submitNote}>
                Add note
              </Button>
            </div>
          </div>
        ) : null}
      </Section>

      {/* 8. Flag this interaction — §12.5 flags an interaction, not an appointment. */}
      <Section title="Flag for review">
        {flagged ? (
          <p className="inline-flex items-center gap-1.5 text-sm text-foreground">
            <Flag className="h-4 w-4" aria-hidden="true" />
            Flagged for Qualicall priority review.
          </p>
        ) : appointment.originatingInteractionId ? (
          <Button variant="outline" size="sm" onClick={onFlag}>
            <Flag className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Flag this interaction
          </Button>
        ) : (
          <p className="text-sm text-muted-foreground">
            This appointment has no originating call or chat, so there is no interaction to flag.
          </p>
        )}
      </Section>
    </Drawer>
  );
}
