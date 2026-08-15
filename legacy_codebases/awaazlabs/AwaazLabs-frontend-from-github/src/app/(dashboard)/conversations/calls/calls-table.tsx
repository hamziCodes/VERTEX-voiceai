'use client';

/**
 * §10.1 Calls table. EXACTLY the ten spec columns, in order:
 *   timestamp · direction · agent · patient name · phone (masked) · duration ·
 *   disposition · triage flag · QA grade (numeric badge) · location.
 *
 * The location column is always rendered (it is one of the ten spec columns); the location
 * *filter* is what §2.4 hides for single-location clinics, not the column.
 *
 * Paginated for a dense list, mirroring the Appointments table. Row click opens the detail
 * drawer; the phone cell stops propagation so the masked-reveal control is independent.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { MaskedValue } from '@/components/ui/masked-value';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
  RowOpenButton, } from '@/components/ui/table';
import { CallDispositionChip, TriageChip } from '@/components/ui/status-chip';
import { formatDateTime, formatDuration, timezoneFor } from '@/lib/format';
import { getLocationById } from '@/mock/orgs';
import type { CallInteractionView, Session } from '@/mock/data-access';
import { AGENT_LABELS } from '@/shared/status-models';

const PAGE_SIZE = 15;

export function CallsTable({
  rows,
  session,
  onRowClick,
  pageResetKey,
}: {
  rows: readonly CallInteractionView[];
  session: Session;
  onRowClick: (id: string) => void;
  /** Changes when filters/sort change — resets pagination. Omit for a stable key. */
  pageResetKey: string;
}): React.JSX.Element {
  const [page, setPage] = useState(1);

  // Reset only when the user changes filters — not when live polling refreshes row data.
  useEffect(() => {
    setPage(1);
  }, [pageResetKey]);

  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));

  // If the result set shrinks, clamp so we are not stranded past the last page.
  useEffect(() => {
    setPage((p) => Math.min(p, pageCount));
  }, [pageCount]);
  const current = Math.min(page, pageCount);
  const pageRows = useMemo(
    () => rows.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE),
    [rows, current],
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-border bg-card">
        <Table caption="Calls, one row per call, newest first.">
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Direction</TableHead>
              <TableHead>Agent</TableHead>
              <TableHead>Patient</TableHead>
              <TableHead>Phone</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Disposition</TableHead>
              <TableHead>Triage</TableHead>
              <TableHead>QA grade</TableHead>
              <TableHead>Location</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageRows.map((call) => {
              const tz = timezoneFor(session.orgId, call.locationId);
              const identity = call.contact?.identity ?? null;
              const name = identity ? `${identity.firstName} ${identity.lastName}` : '—';
              const locationName = call.locationName ?? getLocationById(session.orgId, call.locationId)?.name ?? call.locationId;

              return (
                <TableRow key={call.id} onClick={() => onRowClick(call.id)}>
                  <TableCell className="whitespace-nowrap">
                    <RowOpenButton onClick={() => onRowClick(call.id)} ariaLabel={`Open call details for ${name}`}>
                      {formatDateTime(call.atUtc, tz)}
                    </RowOpenButton>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {call.direction === 'inbound' ? 'Inbound' : 'Outbound'}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">{AGENT_LABELS[call.agent]}</TableCell>
                  <TableCell className="whitespace-nowrap">{name}</TableCell>
                  <TableCell className="whitespace-nowrap">
                    {identity ? (
                      <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                        <MaskedValue identity={identity} session={session} objectRef={`interaction:${call.id}`} />
                      </span>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">{formatDuration(call.durationSeconds)}</TableCell>
                  <TableCell>
                    <CallDispositionChip status={call.disposition} />
                  </TableCell>
                  <TableCell>
                    <TriageChip status={call.triage} />
                  </TableCell>
                  <TableCell>
                    {call.grade ? (
                      <Badge variant="outline">
                        <span className="tabular-nums">{call.grade.overall}</span>
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">{locationName}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {rows.length === 0
            ? 'No matching calls'
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
