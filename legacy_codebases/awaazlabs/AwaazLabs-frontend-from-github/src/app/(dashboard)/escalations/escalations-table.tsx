'use client';

/**
 * §11.1 table. Nine columns, in order:
 *   timestamp · patient name · source interaction (link) · trigger · routed to ·
 *   acknowledged (yes/no + timestamp) · aging · resolution note · location
 *
 * Eight columns trace to §11.1; the "Aging" column is the §11.2 aging indicator
 * (AgingBadge on rows open past their acknowledgement threshold), placed next to the
 * "Acknowledged" column it qualifies.
 *
 * The detail drawer opens from the patient-name `RowOpenButton` (keyboard-reachable, named).
 * The acknowledgement control (one tap, §11.2) renders inline in the Acknowledged column
 * only when `canAck`; a Viewer sees a read-only "No". Appending an outcome note opens the
 * drawer via the note column's "Add note" button.
 */

import React from 'react';
import Link from 'next/link';
import { Link as LinkIcon } from 'lucide-react';

import { AgingBadge } from '@/components/ui/aging-badge';
import { Button } from '@/components/ui/button';
import { RowOpenButton, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { EscalationRowVM } from './types';

export function EscalationsTable({
  rows,
  canAck,
  onAcknowledge,
  onOpenRow,
}: {
  rows: readonly EscalationRowVM[];
  canAck: boolean;
  onAcknowledge: (id: string) => void;
  onOpenRow: (id: string) => void;
}): React.JSX.Element {
  return (
    <Table caption="Safety escalations and clinical-question routing, most recent first.">
      <TableHeader>
        <TableRow>
          <TableHead>Timestamp</TableHead>
          <TableHead>Patient</TableHead>
          <TableHead>Source</TableHead>
          <TableHead>Trigger</TableHead>
          <TableHead>Routed to</TableHead>
          <TableHead>Acknowledged</TableHead>
          <TableHead>Aging</TableHead>
          <TableHead>Resolution note</TableHead>
          <TableHead>Location</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.record.id}>
            <TableCell className="whitespace-nowrap text-muted-foreground tabular-nums">
              {row.timestampLabel}
            </TableCell>
            <TableCell>
              <RowOpenButton
                onClick={() => onOpenRow(row.record.id)}
                ariaLabel={`Open escalation for ${row.patientName}`}
              >
                {row.patientName}
              </RowOpenButton>
            </TableCell>
            <TableCell>
              {row.source ? (
                <Link
                  href={row.source.href}
                  className="inline-flex items-center gap-1 text-foreground underline underline-offset-2 hover:no-underline"
                >
                  <LinkIcon className="h-3.5 w-3.5" aria-hidden="true" />
                  {row.source.kind === 'call' ? 'Call' : 'Chat'}
                </Link>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell>{row.triggerLabel}</TableCell>
            <TableCell className="text-muted-foreground">{row.record.routedTo}</TableCell>
            <TableCell>
              {row.acknowledgedAtUtc ? (
                <span className="text-sm text-foreground">
                  <span className="font-medium">Yes</span>
                  <span className="text-muted-foreground">
                    {' · '}
                    {row.ackTimestampLabel}
                    {row.acknowledgedBy ? ` · ${row.acknowledgedBy}` : ''}
                  </span>
                </span>
              ) : canAck ? (
                <Button size="sm" onClick={() => onAcknowledge(row.record.id)}>
                  Acknowledge
                </Button>
              ) : (
                <span className="text-muted-foreground">No</span>
              )}
            </TableCell>
            <TableCell>
              {row.pastThreshold ? (
                <AgingBadge hours={row.ageHours} label="past threshold" />
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell>
              {row.resolutionNote ? (
                <span className="text-sm text-foreground">{row.resolutionNote}</span>
              ) : canAck ? (
                <Button variant="outline" size="sm" onClick={() => onOpenRow(row.record.id)}>
                  Add note
                </Button>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell className="text-muted-foreground">{row.locationName}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
