'use client';

/**
 * §8.1 worklist table — exactly ten columns:
 *   patient name · payer · plan · status · linked appointment date · assigned-to ·
 *   age in queue · last attempt timestamp · attempts count · location
 *
 * Row aging SLA indicator via `agingLevel(record)` + `AgingBadge`: amber past 24h in a
 * non-terminal state, red past 48h. `agingLevel` returns 'none' for terminal rows and for
 * fresh non-terminal rows, so only rows that actually breach the SLA wear the badge; the
 * rest show a plain age. Thresholds come from `VOB_AGING_THRESHOLD_HOURS` (never hardcoded).
 *
 * The optional leading checkbox column (bulk-retry selection, §8.4) renders only when the
 * session may perform workflow actions — a Viewer never sees it.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

import { AgingBadge } from '@/components/ui/aging-badge';
import { Button } from '@/components/ui/button';
import { VobStatusChip } from '@/components/ui/status-chip';
import { RowOpenButton, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { VobRowVM } from './types';

const PAGE_SIZE = 15;

export function VobWorklistTable({
  rows,
  canAct,
  selectedIds,
  onToggle,
  onToggleAll,
  onOpenRow,
  pageResetKey,
}: {
  rows: readonly VobRowVM[];
  canAct: boolean;
  selectedIds: ReadonlySet<string>;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
  onOpenRow: (id: string) => void;
  /** Changes when filters change — resets pagination. */
  pageResetKey: string;
}) {
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [pageResetKey]);

  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));

  useEffect(() => {
    setPage((p) => Math.min(p, pageCount));
  }, [pageCount]);

  const current = Math.min(page, pageCount);
  const pageRows = useMemo(
    () => rows.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE),
    [rows, current],
  );

  const allSelected = rows.length > 0 && rows.every((r) => selectedIds.has(r.record.id));

  return (
    <div className="flex flex-col gap-3">
      <Table caption="VOB verification worklist">
      <TableHeader>
        <TableRow>
          {canAct ? (
            <TableHead className="w-10">
              <input
                type="checkbox"
                aria-label="Select all filtered rows"
                checked={allSelected}
                onChange={onToggleAll}
                className="h-4 w-4 rounded border-input"
              />
            </TableHead>
          ) : null}
          <TableHead>Patient</TableHead>
          <TableHead>Payer</TableHead>
          <TableHead>Plan</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Appointment</TableHead>
          <TableHead>Assigned to</TableHead>
          <TableHead>Age in queue</TableHead>
          <TableHead>Last attempt</TableHead>
          <TableHead className="text-right">Attempts</TableHead>
          <TableHead>Location</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {pageRows.map((r) => (
          <TableRow key={r.record.id} onClick={() => onOpenRow(r.record.id)}>
            {canAct ? (
              <TableCell>
                <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                  <input
                    type="checkbox"
                    aria-label={`Select ${r.patientName}`}
                    checked={selectedIds.has(r.record.id)}
                    onChange={() => onToggle(r.record.id)}
                    className="h-4 w-4 rounded border-input"
                  />
                </span>
              </TableCell>
            ) : null}
            <TableCell>
              <RowOpenButton
                onClick={() => onOpenRow(r.record.id)}
                ariaLabel={`Open verification details for ${r.patientName}`}
              >
                {r.patientName}
              </RowOpenButton>
            </TableCell>
            <TableCell>{r.record.payer}</TableCell>
            <TableCell className="text-muted-foreground">{r.record.plan}</TableCell>
            <TableCell>
              <VobStatusChip status={r.effectiveStatus} />
            </TableCell>
            <TableCell className="text-muted-foreground tabular-nums">{r.linkedApptDate}</TableCell>
            <TableCell className="text-muted-foreground">{r.effectiveAssignedTo ?? '—'}</TableCell>
            <TableCell>
              {r.agingLevel === 'none' ? (
                <span className="text-sm text-muted-foreground tabular-nums">{r.ageLabel}</span>
              ) : (
                <AgingBadge hours={r.ageHours} />
              )}
            </TableCell>
            <TableCell className="text-muted-foreground tabular-nums">{r.lastAttempt}</TableCell>
            <TableCell className="text-right tabular-nums">{r.attemptsCount}</TableCell>
            <TableCell className="text-muted-foreground">{r.locationName}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {rows.length === 0
            ? 'No matching verifications'
            : `Showing ${(current - 1) * PAGE_SIZE + 1}–${Math.min(current * PAGE_SIZE, rows.length)} of ${rows.length}`}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={current <= 1}
            onClick={() => setPage(current - 1)}
            aria-label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </Button>
          <span className="tabular-nums">
            Page {current} of {pageCount}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={current >= pageCount}
            onClick={() => setPage(current + 1)}
            aria-label="Next page"
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}
