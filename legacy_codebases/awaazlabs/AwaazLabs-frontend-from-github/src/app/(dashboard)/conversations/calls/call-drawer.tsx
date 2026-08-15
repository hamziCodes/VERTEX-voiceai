'use client';

/**
 * §10.1 Call detail drawer. All row-detail sub-items:
 *   1. Audio player for the recording — role-gated, playback audited (playRecording).
 *   2. Full transcript with speaker labels and PII redaction markers.
 *   3. Recording-consent disclosure event — only when two-party consent was active.
 *   4. QA grade breakdown inline — <GradeBreakdown grade={call.grade} /> (§12.3).
 *   5. Linked objects: appointment, VOB record, review request, campaign.
 *   6. Flag this interaction.
 *
 * Gating is structural: a Viewer / NON-PHI session receives `media: null` from the
 * data-access layer, so there is no recordingUrl and no transcript to reach — the audio
 * player and transcript simply are not rendered (no disabled player, no faked waveform).
 *
 * Auditing: `viewTranscript` fires when the drawer opens (transcript is on screen);
 * `playRecording` fires the first time the recording is played. Both refuse-then-audit in
 * the data-access layer, so they are wrapped defensively.
 */

import React, { useEffect, useRef } from 'react';
import Link from 'next/link';
import { CalendarDays, ClipboardCheck, ExternalLink, Flag, Megaphone, Star } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Drawer } from '@/components/ui/drawer';
import { RecordingPlayer, validRecordingUrl } from '@/components/ui/recording-player';
import { CallDispositionChip, TriageChip } from '@/components/ui/status-chip';
import { formatDateTime, formatDuration, timezoneFor } from '@/lib/format';
import { getLocationById } from '@/mock/orgs';
import { playRecording, viewTranscript, type CallInteractionView, type Session } from '@/mock/data-access';
import { AGENT_LABELS, CALL_DISPOSITION_LABELS } from '@/shared/status-models';
import { GradeBreakdown } from '@/components/quality/grade-breakdown';
import { LiveTranscriptLines } from '@/components/live/live-transcript';

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

interface LinkedObject {
  readonly href: string;
  readonly label: string;
  readonly icon: React.ReactNode;
}

export function CallDrawer({
  call,
  session,
  flagged,
  onFlag,
  onClose,
}: {
  call: CallInteractionView;
  session: Session;
  flagged: boolean;
  onFlag: () => void;
  onClose: () => void;
}): React.JSX.Element {
  const tz = timezoneFor(session.orgId, call.locationId);
  const identity = call.contact?.identity ?? null;
  const name = identity ? `${identity.firstName} ${identity.lastName}` : 'Unmatched caller';
  const locationName = call.locationName ?? getLocationById(session.orgId, call.locationId)?.name ?? call.locationId;
  const media = call.media;
  const recordingUrl = validRecordingUrl(media?.recordingUrl);
  const hasRecording = recordingUrl !== null;

  // §2.3 / §10.1: opening the drawer surfaces the transcript, which is an audited event.
  // Guarded on `media` (present only when the session may access it) and wrapped so a
  // denied read can never throw into render.
  useEffect(() => {
    if (!media) return;
    try {
      viewTranscript(session, call.id);
    } catch {
      /* refused in data-access; nothing to surface */
    }
  }, [session, call.id, media]);

  const playAudited = useRef(false);
  const handlePlay = () => {
    if (playAudited.current) return;
    playAudited.current = true;
    try {
      playRecording(session, call.id);
    } catch {
      /* refused in data-access; the native player simply plays nothing meaningful */
    }
  };

  const linkedCandidates: readonly (LinkedObject | null)[] = [
    call.linked.appointmentId
      ? { href: '/appointments', label: 'Appointment created', icon: <CalendarDays className="h-4 w-4" aria-hidden="true" /> }
      : null,
    call.linked.vobId
      ? { href: '/vob-queue', label: 'VOB record', icon: <ClipboardCheck className="h-4 w-4" aria-hidden="true" /> }
      : null,
    call.linked.reviewRequestId
      ? { href: '/reviews', label: 'Review request', icon: <Star className="h-4 w-4" aria-hidden="true" /> }
      : null,
    call.linked.campaignId
      ? { href: '/campaigns', label: 'Campaign', icon: <Megaphone className="h-4 w-4" aria-hidden="true" /> }
      : null,
  ];
  const linkedObjects: readonly LinkedObject[] = linkedCandidates.filter((o): o is LinkedObject => o !== null);

  return (
    <Drawer
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={name}
      description={`${call.direction === 'inbound' ? 'Inbound' : 'Outbound'} · ${AGENT_LABELS[call.agent]} · ${CALL_DISPOSITION_LABELS[call.disposition]}`}
    >
      {/* Call record */}
      <Section title="Call record">
        <dl className="grid grid-cols-2 gap-4">
          <Field label="Time">{formatDateTime(call.atUtc, tz)}</Field>
          <Field label="Direction">{call.direction === 'inbound' ? 'Inbound' : 'Outbound'}</Field>
          <Field label="Agent">{AGENT_LABELS[call.agent]}</Field>
          <Field label="Duration">{formatDuration(call.durationSeconds)}</Field>
          <Field label="Disposition">
            <CallDispositionChip status={call.disposition} />
          </Field>
          <Field label="Triage">
            <TriageChip status={call.triage} />
          </Field>
          <Field label="Location">{locationName}</Field>
          <Field label="Call back number">
            {call.callbackNumberMasked ? (
              <span className="tabular-nums">{call.callbackNumberMasked}</span>
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </Field>
          <Field label="QA grade">
            {call.grade ? (
              <span className="tabular-nums font-semibold text-foreground">{call.grade.overall}</span>
            ) : (
              <span className="text-muted-foreground">Not graded</span>
            )}
          </Field>
        </dl>
      </Section>

      {/* 1. Audio player — rendered only when a real recording URL crossed the data boundary. */}
      {hasRecording ? (
        <Section title="Recording">
          <RecordingPlayer recordingUrl={recordingUrl} label={`recording of the call with ${name}`} onPlay={handlePlay} />
        </Section>
      ) : media ? (
        <Section title="Recording">
          <p className="text-sm text-muted-foreground">Recording is not available yet for this call.</p>
        </Section>
      ) : null}

      {/* 3. Recording-consent disclosure event — only when two-party consent was active
          (the fixture sets consentDisclosureAtUtc only for two-party locations). */}
      {media?.consentDisclosureAtUtc ? (
        <Section title="Recording-consent disclosure">
          <div className="flex flex-col gap-0.5 border-l-2 border-border pl-3">
            <span className="text-sm font-medium text-foreground">Recording disclosure delivered to caller</span>
            <span className="text-xs text-muted-foreground">
              {formatDateTime(media.consentDisclosureAtUtc, tz)} · two-party consent location
            </span>
          </div>
        </Section>
      ) : null}

      {/* 2. Full transcript with speaker labels and PII redaction markers. */}
      {media ? (
        <Section title="Transcript">
          {media.transcript.length === 0 ? (
            <p className="text-sm text-muted-foreground">No transcript available for this call.</p>
          ) : (
            <LiveTranscriptLines
              turns={media.transcript}
              timeZone={tz}
              callId={call.id}
              finalizePending={call.disposition !== 'in_progress'}
              playbackMode={call.disposition === 'in_progress' ? 'live' : 'settled'}
            />
          )}
        </Section>
      ) : (
        <Section title="Recording and transcript">
          <p className="text-sm text-muted-foreground">
            Recordings and transcripts require Manager or Owner access in PHI mode.
          </p>
        </Section>
      )}

      {/* 4. QA grade breakdown inline (§12.3). */}
      {call.grade ? (
        <Section title="QA grade breakdown">
          <GradeBreakdown grade={call.grade} />
        </Section>
      ) : null}

      {/* 5. Linked objects. */}
      <Section title="Linked records">
        {linkedObjects.length === 0 ? (
          <p className="text-sm text-muted-foreground">No linked records for this call.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {linkedObjects.map((o) => (
              <li key={o.href}>
                <Link
                  href={o.href}
                  className="inline-flex items-center gap-1.5 text-sm text-foreground hover:underline"
                >
                  {o.icon}
                  {o.label}
                  <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* 6. Flag this interaction (§12.5). */}
      <Section title="Flag for review">
        {flagged ? (
          <p className="inline-flex items-center gap-1.5 text-sm text-foreground">
            <Flag className="h-4 w-4" aria-hidden="true" />
            Flagged for Qualicall priority review.
          </p>
        ) : (
          <Button variant="outline" size="sm" onClick={onFlag}>
            <Flag className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Flag this interaction
          </Button>
        )}
      </Section>
    </Drawer>
  );
}
