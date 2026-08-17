'use client';

/**
 * §5.2 Appointments table. EXACTLY 12 columns (BUILD_NOTES B4 — the guide's "13" is a
 * miscount): date/time, patient name, phone, treatment, source, language, insurance
 * captured, VOB status chip, triage flag, status, booked by, and location (12th, rendered
 * only when the org is multi-location per §2.4).
 *
 * Paginated. Client-side sort + filter (§5.2 says "server-side"; there is no server, so the
 * same behavior is implemented against the fixture — noted in the audit).
 */

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, ChevronsUpDown } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { MaskedValue } from '@/components/ui/masked-value';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  RowOpenButton,
} from '@/components/ui/table';
import { AppointmentStatusChip, TriageChip, VobStatusChip } from '@/components/ui/status-chip';
import { formatDateTime } from '@/lib/format';
import { timezoneFor } from '@/lib/format';
import { getLocationById } from '@/mock/orgs';
import type { AppointmentView, Session } from '@/mock/data-access';
import {
  AGENT_LABELS,
  APPOINTMENT_SOURCE_LABELS,
  LANGUAGE_LABELS,
  type VobStatus,
} from '@/shared/status-models';

import type { SortKey, SortState } from './types';

const PAGE_SIZE = 12;

function SortHeader({
  label,
  columnKey,
  sort,
  onSortChange,
  className,
}: {
  label: string;
  columnKey: SortKey;
  sort: SortState;
  onSortChange: (next: SortState) => void;
  className?: string;
}) {
  const active = sort.key === columnKey;
  const Icon = !active ? ChevronsUpDown : sort.dir === 'asc' ? ArrowUp : ArrowDown;
  return (
    <TableHead className={className}>
      <button
        type="button"
        onClick={() =>
          onSortChange(
            active ? { key: columnKey, dir: sort.dir === 'asc' ? 'desc' : 'asc' } : { key: columnKey, dir: 'asc' },
          )
        }
        aria-label={`Sort by ${label}${active ? (sort.dir === 'asc' ? ', ascending' : ', descending') : ''}`}
        className="inline-flex items-center gap-1 font-medium text-muted-foreground hover:text-foreground"
      >
        <span>{label}</span>
        <Icon className="h-3 w-3" aria-hidden="true" />
      </button>
    </TableHead>
  );
}

export function AppointmentsTable({
  rows,
  session,
  sort,
  onSortChange,
  vobStatusById,
  onRowClick,
  showLocation,
  pageResetKey,
}: {
  rows: readonly AppointmentView[];
  session: Session;
  sort: SortState;
  onSortChange: (next: SortState) => void;
  vobStatusById: ReadonlyMap<string, VobStatus>;
  onRowClick: (id: string) => void;
  showLocation: boolean;
  /** Changes when filters/sort/bucket change — not on live data refresh. */
  pageResetKey: string;
}) {
  const [page, setPage] = useState(1);

  // Filters or sort changing collapses the result set; return to the first page so the
  // user is never stranded on a page that no longer exists.
  useEffect(() => {
    setPage(1);
  }, [pageResetKey]);

  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));

  // If the result set shrinks, clamp the page index without resetting on every poll.
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
        <Table caption="Appointments, one row per appointment, sortable and filterable.">
          <TableHeader>
            <TableRow>
              <SortHeader label="Date and time" columnKey="datetime" sort={sort} onSortChange={onSortChange} />
              <SortHeader label="Patient" columnKey="name" sort={sort} onSortChange={onSortChange} />
              <TableHead>Phone</TableHead>
              <TableHead>Treatment</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Language</TableHead>
              <TableHead>Insurance</TableHead>
              <TableHead>VOB</TableHead>
              <SortHeader label="Triage" columnKey="triage" sort={sort} onSortChange={onSortChange} />
              <SortHeader label="Status" columnKey="status" sort={sort} onSortChange={onSortChange} />
              <SortHeader label="Booked by" columnKey="booked" sort={sort} onSortChange={onSortChange} />
              {showLocation ? <TableHead>Location</TableHead> : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageRows.map((appt) => {
              const tz = timezoneFor(session.orgId, appt.locationId);
              const identity = appt.contact.identity;
              const name = identity ? `${identity.firstName} ${identity.lastName}` : '—';
              const vobStatus = appt.vobId ? vobStatusById.get(appt.vobId) ?? null : null;
              const locationName = appt.locationName ?? getLocationById(session.orgId, appt.locationId)?.name ?? appt.locationId;

              return (
                // §5.4: the whole row opens the drawer. `TableRow` supplies focus,
                // role="button", and Enter/Space activation, so no nested <button> is
                // needed — one would be an interactive control inside another.
                <TableRow key={appt.id} onClick={() => onRowClick(appt.id)}>
                  <TableCell className="whitespace-nowrap">
                    <RowOpenButton
                      onClick={() => onRowClick(appt.id)}
                      ariaLabel={`Open appointment details for ${name}`}
                    >
                      {formatDateTime(appt.startsAtUtc, tz)}
                    </RowOpenButton>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">{name}</TableCell>
                  <TableCell className="whitespace-nowrap">
                    {identity ? (
                      <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                        <MaskedValue
                          identity={identity}
                          session={session}
                          objectRef={`appointment:${appt.id}`}
                        />
                      </span>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell>{appt.serviceInterest}</TableCell>
                  <TableCell className="whitespace-nowrap">{APPOINTMENT_SOURCE_LABELS[appt.source]}</TableCell>
                  <TableCell className="whitespace-nowrap">{LANGUAGE_LABELS[appt.language]}</TableCell>
                  <TableCell>
                    <Badge variant={appt.insuranceCaptured ? 'outline' : 'secondary'}>
                      {appt.insuranceCaptured ? 'Yes' : 'No'}
                    </Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {vobStatus ? (
                      <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                        <Link
                          href="/vob-queue"
                          aria-label={`View VOB record for ${name}`}
                          className="rounded-md hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-ring"
                        >
                          <VobStatusChip status={vobStatus} abbreviated />
                        </Link>
                      </span>
                    ) : (
                      <span className="text-muted-foreground">None</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <TriageChip status={appt.triage} />
                  </TableCell>
                  <TableCell>
                    <AppointmentStatusChip status={appt.status} />
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    <div className="flex flex-col">
                      <span>{AGENT_LABELS[appt.bookedByAgent]}</span>
                      <span className="text-xs text-muted-foreground">
                        {formatDateTime(appt.bookedAtUtc, tz)}
                      </span>
                    </div>
                  </TableCell>
                  {showLocation ? (
                    <TableCell className="whitespace-nowrap">{locationName}</TableCell>
                  ) : null}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {rows.length === 0
            ? 'No matching appointments'
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
