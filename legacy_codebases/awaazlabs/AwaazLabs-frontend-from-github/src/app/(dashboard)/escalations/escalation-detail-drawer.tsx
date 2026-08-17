'use client';

/**
 * §11.2 acknowledgement workflow surface.
 *
 * "Any Manager or Owner can acknowledge (one tap, audited) and append an outcome note."
 *
 * Gating: the whole action surface renders only when `canAck` is true
 * (`canAcknowledgeEscalation(session)` — a Viewer never sees it). The append-note action
 * additionally goes through `recordNoteEdit`, which refuses structurally for a Viewer.
 *
 * AUDIT (see progress/escalations_audit.md and the final report): §2.3 enumerates exactly
 * twelve audit event types and NONE is `escalation_acknowledged`. Per the task's instruction
 * and BUILD_NOTES B14's precedent, no thirteenth type is invented:
 *   - The bare acknowledgement tap writes NO audit event (there is no truthful type for it).
 *   - Appending an outcome note writes the existing, truthful `note_edit` event, via
 *     `recordNoteEdit`.
 */

import React, { useState } from 'react';
import { Link as LinkIcon } from 'lucide-react';
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Drawer } from '@/components/ui/drawer';
import { EscalationStatusChip } from '@/components/ui/status-chip';
import { AgingBadge } from '@/components/ui/aging-badge';
import { ESCALATION_TRIGGER_LABELS } from '@/shared/status-models';

import type { EscalationRowVM } from './types';

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm text-foreground">{children}</dd>
    </div>
  );
}

export function EscalationDetailDrawer({
  row,
  open,
  onOpenChange,
  canAck,
  onAcknowledge,
  onSaveNote,
}: {
  row: EscalationRowVM;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  canAck: boolean;
  onAcknowledge: (id: string) => void;
  onSaveNote: (id: string, note: string) => void;
}): React.JSX.Element {
  const [note, setNote] = useState(row.resolutionNote ?? '');
  const isOpen = row.effectiveStatus === 'open';

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={`Escalation — ${row.patientName}`}
      description={ESCALATION_TRIGGER_LABELS[row.record.trigger]}
    >
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center gap-2">
          <EscalationStatusChip status={row.effectiveStatus} />
          {row.pastThreshold ? <AgingBadge hours={row.ageHours} label="past threshold" /> : null}
        </div>

        <dl className="grid grid-cols-2 gap-4">
          <Field label="Timestamp">{row.timestampLabel}</Field>
          <Field label="Location">{row.locationName}</Field>
          <Field label="Trigger">{row.triggerLabel}</Field>
          <Field label="Routed to">{row.record.routedTo}</Field>
          <Field label="Source interaction">
            {row.source ? (
              <Link
                href={row.source.href}
                className="inline-flex items-center gap-1 font-medium text-foreground underline underline-offset-2 hover:no-underline"
              >
                <LinkIcon className="h-3.5 w-3.5" aria-hidden="true" />
                {row.source.kind === 'call' ? 'View call' : 'View chat'}
              </Link>
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </Field>
          <Field label="Acknowledged">
            {row.acknowledgedAtUtc ? (
              <span>
                Yes · {row.ackTimestampLabel}
                {row.acknowledgedBy ? ` · ${row.acknowledgedBy}` : ''}
              </span>
            ) : (
              <Badge variant="outline">No</Badge>
            )}
          </Field>
        </dl>

        {canAck ? (
          <div className="flex flex-col gap-4 border-t border-border pt-6">
            {isOpen ? (
              <div className="flex flex-col gap-2">
                <p className="text-sm text-muted-foreground">
                  Acknowledge this escalation to record that a Manager or Owner has taken ownership.
                </p>
                <div>
                  <Button onClick={() => onAcknowledge(row.record.id)}>Acknowledge</Button>
                </div>
              </div>
            ) : null}

            <div className="flex flex-col gap-2">
              <label htmlFor="escalation-note" className="text-sm font-medium text-foreground">
                Outcome note
              </label>
              <textarea
                id="escalation-note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={4}
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="Describe how this escalation was handled…"
              />
              <div>
                <Button
                  variant="secondary"
                  disabled={note.trim() === '' || note.trim() === (row.resolutionNote ?? '')}
                  onClick={() => onSaveNote(row.record.id, note.trim())}
                >
                  Save note
                </Button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </Drawer>
  );
}
