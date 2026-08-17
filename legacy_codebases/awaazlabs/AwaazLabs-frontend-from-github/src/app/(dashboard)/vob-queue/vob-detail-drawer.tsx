'use client';

/**
 * §8.2 row detail drawer + §8.3 row actions.
 *
 * Renders the verification record: captured benefits, prior-auth / referral flags, the
 * per-attempt call log (with recording + transcript when the projection carries media —
 * a Viewer / NON-PHI session receives `media: null`, so nothing is rendered rather than a
 * disabled player), payer reference numbers, and the optimistic status timeline.
 *
 * The four actions each call `recordVobQueueAction` (audited) via the parent, then update
 * the timeline optimistically. The whole actions block is gated on `canAct`
 * (`canPerformWorkflowActions`) — a Viewer sees none of it.
 */

import React, { useMemo, useRef, useState } from 'react';
import { FileText, Flag } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Drawer } from '@/components/ui/drawer';
import { RecordingPlayer, validRecordingUrl } from '@/components/ui/recording-player';
import { Select } from '@/components/ui/select';
import { VobStatusChip } from '@/components/ui/status-chip';
import { formatDateTime, formatDuration, formatUsd } from '@/lib/format';
import {
  PermissionDeniedError,
  playRecording,
  viewTranscript,
  type CallInteractionView,
  type Session,
} from '@/mock/data-access';
import { submitFlag } from '@/shared/flag-store';
import {
  VOB_RESOLVE_REASONS,
  VOB_RESOLVE_REASON_LABELS,
  type VobResolveReason,
} from '@/shared/status-models';
import type { DisplayTimelineEntry, VobOverride, VobRowVM } from './types';

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-md border border-border p-3">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-foreground">{value}</dd>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="text-sm font-semibold text-foreground">{children}</h3>;
}

function AttemptCallLog({
  row,
  session,
  resolveCall,
}: {
  row: VobRowVM;
  session: Session;
  resolveCall: (interactionId: string) => CallInteractionView | undefined;
}) {
  const playAuditedRef = useRef<Record<string, boolean>>({});
  const [transcripts, setTranscripts] = useState<Record<string, boolean>>({});
  const [flagged, setFlagged] = useState<Record<string, boolean>>({});

  const attempts = row.record.attempts;
  if (attempts.length === 0) {
    return <p className="text-sm text-muted-foreground">No call attempts recorded yet.</p>;
  }

  return (
    <ol className="flex flex-col gap-3">
      {attempts.map((attempt, i) => {
        const call = attempt.interactionId ? resolveCall(attempt.interactionId) : undefined;
        const media = call?.media ?? null;
        const recordingUrl = validRecordingUrl(media?.recordingUrl);
        const showTranscript = attempt.interactionId ? transcripts[attempt.interactionId] : false;

        const handlePlay = () => {
          if (!attempt.interactionId) return;
          if (playAuditedRef.current[attempt.interactionId]) return;
          playAuditedRef.current[attempt.interactionId] = true;
          try {
            playRecording(session, attempt.interactionId);
          } catch (e) {
            if (!(e instanceof PermissionDeniedError)) throw e;
          }
        };
        const handleTranscript = () => {
          if (!attempt.interactionId) return;
          try {
            viewTranscript(session, attempt.interactionId);
            setTranscripts((t) => ({ ...t, [attempt.interactionId as string]: true }));
          } catch (e) {
            if (!(e instanceof PermissionDeniedError)) throw e;
          }
        };

        return (
          <li key={`${attempt.at}-${i}`} className="rounded-md border border-border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium text-foreground">
                {formatDateTime(attempt.at, row.timezone)}
              </span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {formatDuration(attempt.durationSeconds)}
              </span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">{attempt.outcome}</p>
            <dl className="mt-2 grid grid-cols-1 gap-1 text-xs sm:grid-cols-2">
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">Payer reference</dt>
                <dd className="font-medium tabular-nums text-foreground">
                  {attempt.payerReferenceNumber ?? '—'}
                </dd>
              </div>
            </dl>

            {/*
              §12.5: "All client-submitted flags (from the Flag this interaction button
              across Appointments, Conversations, VOB Queue) land here."
              §8.3 does not list Flag among its four row actions, but §12.5 names VOB Queue
              as a flag source, so the button is traceable to that bullet. It flags the
              *interaction* (this call attempt), not the verification record. Flagging
              writes to the flag store, never the audit log — see BUILD_NOTES § B14.
            */}
            {attempt.interactionId ? (
              <div className="mt-2">
                {flagged[attempt.interactionId] ? (
                  <p className="inline-flex items-center gap-1.5 text-xs text-foreground">
                    <Flag className="h-3.5 w-3.5" aria-hidden="true" />
                    Flagged for Qualicall priority review.
                  </p>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    aria-label={`Flag the call attempt on ${formatDateTime(attempt.at, row.timezone)} for review`}
                    onClick={() => {
                      const interactionId = attempt.interactionId;
                      if (!interactionId) return;
                      submitFlag({
                        orgId: session.orgId,
                        interactionId,
                        submittedBy: session.actor,
                        reason: `Flagged from VOB queue record ${row.record.id} by ${session.actor}`,
                      });
                      setFlagged((f) => ({ ...f, [interactionId]: true }));
                    }}
                  >
                    <Flag className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                    Flag this interaction
                  </Button>
                )}
              </div>
            ) : null}

            {media ? (
              <div className="mt-3 flex flex-col gap-2">
                {recordingUrl ? (
                  <RecordingPlayer
                    recordingUrl={recordingUrl}
                    label={`VOB attempt recording on ${formatDateTime(attempt.at, row.timezone)}`}
                    onPlay={handlePlay}
                  />
                ) : (
                  <p className="text-sm text-muted-foreground">Recording is not available yet for this attempt.</p>
                )}
                <Button variant="outline" size="sm" onClick={handleTranscript} className="w-fit">
                  <FileText className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                  View transcript
                </Button>
                {showTranscript ? (
                  <div className="max-h-48 overflow-y-auto rounded-md bg-muted p-3 text-xs">
                    {media.transcript.map((turn, ti) => (
                      <p key={ti} className="mb-1.5 last:mb-0">
                        <span className="font-semibold capitalize text-foreground">{turn.speaker}: </span>
                        <span className="text-muted-foreground">{turn.text}</span>
                      </p>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function StatusTimeline({ entries, timezone }: { entries: readonly DisplayTimelineEntry[]; timezone: string }) {
  return (
    <ol className="flex flex-col gap-2 border-l border-border pl-4">
      {entries.map((e, i) => (
        <li key={`${e.at}-${i}`} className="relative">
          <span
            className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-border"
            aria-hidden="true"
          />
          <div className="flex flex-wrap items-center gap-2">
            <VobStatusChip status={e.status} />
            <span className="text-xs text-muted-foreground tabular-nums">
              {formatDateTime(e.at, timezone)}
            </span>
            <span className="text-xs text-muted-foreground">· {e.actor}</span>
          </div>
          {e.note ? <p className="mt-0.5 text-xs text-muted-foreground">{e.note}</p> : null}
        </li>
      ))}
    </ol>
  );
}

export function VobDetailDrawer({
  row,
  override,
  open,
  onOpenChange,
  session,
  canAct,
  resolveCall,
  onRetry,
  onResolve,
  onEscalate,
  onAddNote,
}: {
  row: VobRowVM;
  override: VobOverride | undefined;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  session: Session;
  canAct: boolean;
  resolveCall: (interactionId: string) => CallInteractionView | undefined;
  onRetry: (id: string) => void;
  onResolve: (id: string, reason: VobResolveReason) => void;
  onEscalate: (id: string, assignee: string) => void;
  onAddNote: (id: string, body: string) => void;
}) {
  const [reason, setReason] = useState<VobResolveReason>(VOB_RESOLVE_REASONS[0]);
  const [assignee, setAssignee] = useState('');
  const [note, setNote] = useState('');

  const rec = row.record;

  const timeline = useMemo<DisplayTimelineEntry[]>(() => {
    const base: DisplayTimelineEntry[] = rec.statusTimeline.map((t) => ({
      at: t.at,
      status: t.status,
      actor: t.actor,
    }));
    const extra = override?.extraTimeline ?? [];
    return [...base, ...extra].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
  }, [rec.statusTimeline, override?.extraTimeline]);

  const notes = useMemo(() => {
    const server = (rec.staffNotes ?? []).map((note) => ({ at: note.at, body: note.body }));
    const extra = override?.extraNotes ?? [];
    return [...server, ...extra].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
  }, [rec.staffNotes, override?.extraNotes]);
  const { benefits } = rec;

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={row.patientName}
      description={`${rec.payer} · ${rec.plan}`}
    >
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center gap-2">
          <VobStatusChip status={row.effectiveStatus} />
          {override?.resolved || rec.resolved ? <Badge variant="outline">Resolved</Badge> : null}
          {rec.priorAuthRequired ? <Badge variant="destructive">Prior auth required</Badge> : null}
          {rec.referralRequired ? <Badge variant="destructive">Referral required</Badge> : null}
        </div>

        <section className="flex flex-col gap-3">
          <SectionTitle>Captured benefits</SectionTitle>
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Field label="Copay" value={benefits.copayUsd !== null ? formatUsd(benefits.copayUsd) : '—'} />
            <Field
              label="Deductible"
              value={benefits.deductibleUsd !== null ? formatUsd(benefits.deductibleUsd) : '—'}
            />
            <Field
              label="Out-of-pocket max"
              value={benefits.outOfPocketMaxUsd !== null ? formatUsd(benefits.outOfPocketMaxUsd) : '—'}
            />
          </dl>
          <div className="rounded-md border border-border p-3">
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Coverage notes</dt>
            <dd className="mt-1 text-sm text-foreground">{benefits.coverageNotes ?? 'None captured.'}</dd>
          </div>
        </section>

        <section className="flex flex-col gap-3">
          <SectionTitle>Prior auth &amp; referral</SectionTitle>
          <dl className="grid grid-cols-2 gap-3">
            <Field label="Prior authorization" value={rec.priorAuthRequired ? 'Required' : 'Not required'} />
            <Field label="Referral" value={rec.referralRequired ? 'Required' : 'Not required'} />
          </dl>
        </section>

        <section className="flex flex-col gap-3">
          <SectionTitle>Call log</SectionTitle>
          <AttemptCallLog row={row} session={session} resolveCall={resolveCall} />
        </section>

        <section className="flex flex-col gap-3">
          <SectionTitle>Status timeline</SectionTitle>
          <StatusTimeline entries={timeline} timezone={row.timezone} />
        </section>

        {notes.length > 0 ? (
          <section className="flex flex-col gap-2">
            <SectionTitle>Notes</SectionTitle>
            {notes.map((n, i) => (
              <div key={`${n.at}-${i}`} className="rounded-md border border-border p-3 text-sm">
                <p className="text-xs text-muted-foreground tabular-nums">
                  {formatDateTime(n.at, row.timezone)}
                </p>
                <p className="mt-1 text-foreground">{n.body}</p>
              </div>
            ))}
          </section>
        ) : null}

        {canAct ? (
          <section className="flex flex-col gap-4 border-t border-border pt-4">
            <SectionTitle>Actions</SectionTitle>

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => onRetry(rec.id)}>
                Retry (re-queue)
              </Button>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-medium text-muted-foreground" id={`resolve-${rec.id}`}>
                Mark resolved — reason
              </label>
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  aria-label="Resolution reason"
                  value={reason}
                  onValueChange={(v) => setReason(v as VobResolveReason)}
                  options={VOB_RESOLVE_REASONS.map((r) => ({
                    value: r,
                    label: VOB_RESOLVE_REASON_LABELS[r],
                  }))}
                />
                <Button variant="secondary" onClick={() => onResolve(rec.id, reason)}>
                  Mark resolved
                </Button>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-medium text-muted-foreground" htmlFor={`escalate-${rec.id}`}>
                Escalate to staff
              </label>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  id={`escalate-${rec.id}`}
                  value={assignee}
                  onChange={(e) => setAssignee(e.target.value)}
                  placeholder="Staff member"
                  className="rounded-md border border-input bg-transparent px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground"
                />
                <Button
                  variant="secondary"
                  disabled={assignee.trim() === ''}
                  onClick={() => {
                    onEscalate(rec.id, assignee.trim());
                    setAssignee('');
                  }}
                >
                  Escalate
                </Button>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-medium text-muted-foreground" htmlFor={`note-${rec.id}`}>
                Add note
              </label>
              <textarea
                id={`note-${rec.id}`}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
                className="rounded-md border border-input bg-transparent px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground"
                placeholder="Append a note to this verification…"
              />
              <div>
                <Button
                  variant="secondary"
                  disabled={note.trim() === ''}
                  onClick={() => {
                    onAddNote(rec.id, note.trim());
                    setNote('');
                  }}
                >
                  Add note
                </Button>
              </div>
            </div>
          </section>
        ) : null}
      </div>
    </Drawer>
  );
}
