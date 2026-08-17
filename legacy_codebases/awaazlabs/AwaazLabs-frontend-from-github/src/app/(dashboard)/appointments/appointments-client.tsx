'use client';

/**
 * §5 Appointments tab — the working surface for front-desk staff. Table-first (§5.2/§5.3),
 * with a secondary calendar toggle (§5.5), a detail drawer (§5.4), a header stats strip
 * (§5.1), and the three empty/degraded states (§5.6).
 *
 * Modes (structural, from the data-access layer, never a local role check):
 *   - PHI + Owner/Manager: full table, phone reveal, workflow actions.
 *   - PHI + Viewer: rows load but the data-access layer omits phoneE164 (no reveal control)
 *     and workflow actions are gated off.
 *   - NON-PHI: listAppointments returns `{ kind: 'aggregate' }`; the union forces the
 *     table to be hidden and only counts render.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CalendarX2 } from 'lucide-react';

import { Banner } from '@/components/ui/banner';
import { ExportCsvButton, ListExportRow } from '@/components/ui/export-csv-button';
import { Card, CardContent } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { StatCard } from '@/components/ui/stat-card';
import { DataTableSkeleton, StatGridSkeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { formatPercent, timezoneFor, formatTime } from '@/lib/format';
import { useLiveAppointments } from '@/hooks/use-dashboard-live';
import {
  addLiveAppointmentNote,
  recordLivePatientSearch,
  updateLiveAppointmentStatus,
  type DashboardStatsDto,
} from '@/lib/dashboard-live';
import { isMultiLocation } from '@/mock/schema';
import { submitFlag } from '@/shared/flag-store';
import type { AppointmentView, GatedRows } from '@/mock/data-access';
import { canExport } from '@/mock/data-access';
import { useSession } from '@/shared/session-context';
import { buildAppointmentsCsv } from '@/app/(dashboard)/reports/csv';
import { filtersToParams, runCsvExport } from '@/lib/csv-export';
import type { AppointmentStatus, VobStatus } from '@/shared/status-models';

import { AppointmentDrawer } from './appointment-drawer';
import { AppointmentsCalendar } from './appointments-calendar';
import { AppointmentsFilters } from './appointments-filters';
import { AppointmentsTable } from './appointments-table';
import { DEFAULT_FILTERS, DEFAULT_SORT, TRIAGE_ORDER, localDateKey, type AppointmentFilters, type SortState } from './types';

type LocalNote = { readonly at: string; readonly author: string; readonly body: string };

const EMPTY_STATS: DashboardStatsDto = {
  bookedToday: 0,
  bookedSameWeekdayLastWeek: 0,
  bookedThisWeek: 0,
  bookingRateThisWeek: null,
  upcomingNext7Days: 0,
  noShowsAndCancellationsThisWeek: 0,
  noShowCancelRateThisWeek: null,
  confirmationRate: null,
  noShowRate30d: null,
  nextAppointment: null,
};

const EMPTY_GATED_APPOINTMENTS: GatedRows<AppointmentView> = { kind: 'rows', rows: [] };

type NextAppointment = { readonly patientName: string; readonly startsAt: string } | null;

function HeaderStats(props: DashboardStatsDto & { tz: string; nextAppointment: NextAppointment }) {
  const pct = (v: number | null) => (v === null ? '—' : formatPercent(v));
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <StatCard label="Booked today" value={props.bookedToday} format="number" />
      <StatCard label="Upcoming next 7 days" value={props.upcomingNext7Days} format="number" />
      <StatCard
        label="Confirmation rate"
        value={pct(props.confirmationRate)}
        format="text"
        tooltip="Confirmed divided by bookings that had a scheduled confirmation attempt."
      />
      <StatCard
        label="No-show rate (30 days)"
        value={pct(props.noShowRate30d)}
        format="text"
        tooltip="No-shows divided by resolved appointments (completed or no-show) over the trailing 30 days."
      />
      <StatCard
        label="Next appointment"
        value={props.nextAppointment ? formatTime(props.nextAppointment.startsAt, props.tz) : 'None'}
        format="text"
        subStats={props.nextAppointment ? [{ label: 'Patient', value: props.nextAppointment.patientName }] : []}
        tooltip="The time and patient name of the immediately next scheduled appointment."
      />
    </div>
  );
}

export function AppointmentsClient() {
  const { session, org } = useSession();
  const tz = session.locationId ? timezoneFor(session.orgId, session.locationId) : 'UTC';

  const { data: live, isLoading: loadingLive, error: liveError, invalidate } = useLiveAppointments();

  const stats = live?.stats ?? EMPTY_STATS;
  const gated: GatedRows<AppointmentView> = live?.gated ?? EMPTY_GATED_APPOINTMENTS;
  const vobStatusById = useMemo<ReadonlyMap<string, VobStatus>>(
    () => live?.vobStatusById ?? new Map<string, VobStatus>(),
    [live],
  );
  const vobById = useMemo(() => new Map<string, never>(), []);

  const [filters, setFilters] = useState<AppointmentFilters>(DEFAULT_FILTERS);
  const [sort, setSort] = useState<SortState>(DEFAULT_SORT);
  const [view, setView] = useState<'table' | 'calendar'>('table');
  const [bucket, setBucket] = useState<'upcoming' | 'status_update'>('upcoming');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [ehrBannerDismissed, setEhrBannerDismissed] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // Local optimistic overlays for §5.4 workflow actions. The audit event is the source of
  // record; these drive the UI so the change is visible without a backend round-trip.
  const [statusOverrides, setStatusOverrides] = useState<Record<string, AppointmentStatus>>({});
  const [notesByAppt, setNotesByAppt] = useState<Record<string, readonly LocalNote[]>>({});
  const [flagged, setFlagged] = useState<ReadonlySet<string>>(new Set());

  // §5.3 "search is audited in PHI mode": debounce keystrokes; recordPatientSearch no-ops
  // outside PHI mode and on empty input, so this is safe to call unconditionally.
  useEffect(() => {
    const q = filters.search;
    const t = setTimeout(() => {
      if (q.trim()) void recordLivePatientSearch(session, q).catch(() => undefined);
    }, 400);
    return () => clearTimeout(t);
  }, [filters.search, session]);

  const baseRows = useMemo<readonly AppointmentView[]>(
    () => (gated.kind === 'rows' ? gated.rows : []),
    [gated],
  );

  const enrichedRows = useMemo<readonly AppointmentView[]>(
    () =>
      baseRows.map((a) => {
        const override = statusOverrides[a.id];
        const extra = notesByAppt[a.id];
        if (!override && !extra) return a;
        return {
          ...a,
          status: override ?? a.status,
          staffNotes: extra ? [...a.staffNotes, ...extra] : a.staffNotes,
        };
      }),
    [baseRows, statusOverrides, notesByAppt],
  );

  const nextAppointment = useMemo<NextAppointment>(() => {
    const now = Date.now();
    const next = enrichedRows
      .filter((a) => {
        const startsAt = new Date(a.startsAtUtc).getTime();
        const activeStatus = !['completed', 'cancelled', 'no_show'].includes(a.status);
        return a.hasScheduledTime !== false && Number.isFinite(startsAt) && activeStatus && !a.needsReview && startsAt >= now;
      })
      .sort((a, b) => new Date(a.startsAtUtc).getTime() - new Date(b.startsAtUtc).getTime())[0];
    if (!next) return null;
    const identity = next.contact.identity;
    return {
      startsAt: next.startsAtUtc,
      patientName: identity ? `${identity.firstName} ${identity.lastName}`.trim() : 'Unknown patient',
    };
  }, [enrichedRows]);

  const bucketedRows = useMemo<readonly AppointmentView[]>(() => {
    const now = Date.now();
    return enrichedRows.filter((a) => {
      const startsAt = new Date(a.startsAtUtc).getTime();
      const activeStatus = !['completed', 'cancelled', 'no_show'].includes(a.status);
      const ready = a.hasScheduledTime !== false && Number.isFinite(startsAt) && activeStatus && !a.needsReview && startsAt >= now;
      return bucket === 'upcoming' ? ready : !ready;
    });
  }, [enrichedRows, bucket]);

  const filtered = useMemo<readonly AppointmentView[]>(() => {
    const q = filters.search.trim().toLowerCase();
    return bucketedRows.filter((a) => {
      if (filters.status !== 'all' && a.status !== filters.status) return false;
      if (filters.source !== 'all' && a.source !== filters.source) return false;
      if (filters.triage !== 'all' && a.triage !== filters.triage) return false;
      if (filters.language !== 'all' && a.language !== filters.language) return false;
      if (filters.locationId !== 'all' && a.locationId !== filters.locationId) return false;

      if (filters.vob !== 'all') {
        const vs = a.vobId ? vobStatusById.get(a.vobId) ?? null : null;
        if (filters.vob === 'none') {
          if (vs !== null) return false;
        } else if (vs !== filters.vob) {
          return false;
        }
      }

      if (filters.dateFrom || filters.dateTo) {
        const key = localDateKey(a.startsAtUtc, timezoneFor(session.orgId, a.locationId));
        if (filters.dateFrom && key < filters.dateFrom) return false;
        if (filters.dateTo && key > filters.dateTo) return false;
      }

      if (q) {
        const id = a.contact.identity;
        const hay = [id ? `${id.firstName} ${id.lastName}` : '', id?.phoneMasked ?? '', id?.phoneE164 ?? '']
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }

      return true;
    });
  }, [bucketedRows, filters, vobStatusById, session.orgId]);

  const sorted = useMemo<readonly AppointmentView[]>(() => {
    const dir = sort.dir === 'asc' ? 1 : -1;
    const arr = [...filtered];
    arr.sort((a, b) => {
      switch (sort.key) {
        case 'booked':
          return (new Date(a.bookedAtUtc).getTime() - new Date(b.bookedAtUtc).getTime()) * dir;
        case 'datetime':
          return (new Date(a.startsAtUtc).getTime() - new Date(b.startsAtUtc).getTime()) * dir;
        case 'name': {
          const an = a.contact.identity ? `${a.contact.identity.lastName} ${a.contact.identity.firstName}` : '';
          const bn = b.contact.identity ? `${b.contact.identity.lastName} ${b.contact.identity.firstName}` : '';
          return an.localeCompare(bn) * dir;
        }
        case 'status':
          return a.status.localeCompare(b.status) * dir;
        case 'triage':
          return (TRIAGE_ORDER[a.triage] - TRIAGE_ORDER[b.triage]) * dir;
        default:
          return 0;
      }
    });
    return arr;
  }, [filtered, sort]);

  const selected = selectedId ? enrichedRows.find((a) => a.id === selectedId) ?? null : null;

  const handleStatusChange = (to: AppointmentStatus) => {
    if (!selected) return;
    setStatusOverrides((prev) => ({ ...prev, [selected.id]: to }));
    void updateLiveAppointmentStatus(session, selected.id, to)
      .then(() => invalidate())
      .catch(() => {
        setStatusOverrides((prev) => {
          const next = { ...prev };
          delete next[selected.id];
          return next;
        });
      });
  };

  const handleAddNote = (body: string) => {
    if (!selected) return;
    void addLiveAppointmentNote(session, selected.id, body).then(() => invalidate()).catch(() => undefined);
    setNotesByAppt((prev) => ({
      ...prev,
      [selected.id]: [...(prev[selected.id] ?? []), { at: new Date().toISOString(), author: session.actor, body }],
    }));
  };

  /**
   * §5.4 / §12.5 "Flag this interaction".
   *
   * Flag is NOT one of the twelve §2.3 audit event types, so no audit event is written —
   * the frozen `AuditEventType` union has no `flag`, and inventing a thirteenth would
   * contradict the spec (BUILD_NOTES § B14). It writes to the shared flag store instead,
   * so the item appears immediately in the §12.5 inbox on the Quality tab.
   *
   * §12.5 flags an *interaction*, not an appointment. An appointment booked through a form
   * has no originating interaction, so there is nothing to flag — the button is disabled
   * in that case rather than silently writing a dangling reference.
   */
  const handleFlag = () => {
    if (!selected?.originatingInteractionId) return;

    submitFlag({
      orgId: session.orgId,
      interactionId: selected.originatingInteractionId,
      submittedBy: session.actor,
      reason: `Flagged from appointment ${selected.id} by ${session.actor}`,
    });

    setFlagged((prev) => {
      const next = new Set(prev);
      next.add(selected.id);
      return next;
    });
  };

  const showLocation = isMultiLocation(org);

  const pageResetKey = useMemo(
    () => JSON.stringify({ filters, sort, bucket }),
    [filters, sort, bucket],
  );
  const canExportRows = canExport(session);
  // §5.6 "EHR sync unavailable" — driven off the org's outcome-data flag (see audit note).
  const ehrSyncUnavailable = !org.outcomeDataAvailable;

  const exportFilterParams = useMemo(
    () =>
      filtersToParams({
        search: filters.search,
        status: filters.status,
        source: filters.source,
        vob: filters.vob,
        triage: filters.triage,
        language: filters.language,
        locationId: filters.locationId,
        dateFrom: filters.dateFrom,
        dateTo: filters.dateTo,
        bucket,
      }),
    [filters, bucket],
  );

  const handleExport = useCallback(() => {
    const error = runCsvExport(
      session,
      'appointments',
      sorted.length,
      exportFilterParams,
      `appointments-${new Date().toISOString().slice(0, 10)}.csv`,
      buildAppointmentsCsv(sorted, session.orgId),
    );
    setExportError(error);
  }, [session, sorted, exportFilterParams]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Appointments"
        description="The working surface for front-desk staff. Table-first, with a calendar toggle."
      />

      {liveError ? (
        <Banner variant="destructive" title="Live appointment data unavailable">
          {liveError}
        </Banner>
      ) : null}

      {exportError ? (
        <Banner variant="destructive" title="Export failed" onDismiss={() => setExportError(null)}>
          {exportError}
        </Banner>
      ) : null}

      {ehrSyncUnavailable && !ehrBannerDismissed ? (
        <Banner variant="default" title="EHR sync unavailable" onDismiss={() => setEhrBannerDismissed(true)}>
          Appointment outcomes are manual-entry until the EHR calendar sync is restored. Use the Completed and No-show
          controls in the detail drawer to keep no-show analytics accurate.
        </Banner>
      ) : null}

      {/* §5.1 header stats strip — aggregates, shown in every mode. */}
      {loadingLive && live === null ? (
        <>
          <span role="status" className="sr-only">
            Loading live appointment data
          </span>
          <StatGridSkeleton cards={5} />
          <DataTableSkeleton rows={8} />
        </>
      ) : (
        <>
          <HeaderStats {...stats} tz={tz} nextAppointment={nextAppointment} />

      {gated.kind === 'aggregate' ? (
        // §5.6 NON-PHI: aggregate counts only, table hidden. The union forces this branch.
        <div className="flex flex-col gap-4">
          <Banner variant="default" title="Aggregate view (NON-PHI mode)">
            This workspace is in NON-PHI mode, so patient-level appointment rows are not available. Only aggregate counts
            are shown.
          </Banner>
          <Card>
            <CardContent className="p-6">
              <p className="text-sm text-muted-foreground">Total appointments in scope</p>
              <p className="mt-1 text-3xl font-semibold tabular-nums text-foreground">{gated.total}</p>
            </CardContent>
          </Card>
        </div>
      ) : baseRows.length === 0 ? (
        // §5.6 "No appointments yet".
        <EmptyState
          icon={<CalendarX2 className="h-8 w-8" />}
          title="No appointments yet"
          description="When patients book through the Receptionist, Chat agents, or a web form, their appointments will appear here."
        />
      ) : (
        <div className="flex flex-col gap-4">
          <AppointmentsFilters
            filters={filters}
            onChange={setFilters}
            locations={org.locations}
            showLocationFilter={showLocation}
          />

          <Tabs value={view} onValueChange={(v) => setView(v === 'calendar' ? 'calendar' : 'table')}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="inline-flex rounded-lg border border-border bg-muted p-1">
                <button
                  type="button"
                  onClick={() => setBucket('upcoming')}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                    bucket === 'upcoming' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground'
                  }`}
                >
                  Upcoming
                </button>
                <button
                  type="button"
                  onClick={() => setBucket('status_update')}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                    bucket === 'status_update' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground'
                  }`}
                >
                  Status update needed
                </button>
              </div>
              <TabsList label="Appointments view">
                <TabsTrigger value="table">Table</TabsTrigger>
                <TabsTrigger value="calendar">Calendar</TabsTrigger>
              </TabsList>
            </div>

            {canExportRows ? (
              <ListExportRow>
                <ExportCsvButton onClick={handleExport} disabled={sorted.length === 0} />
              </ListExportRow>
            ) : null}

            <TabsContent value="table" className="mt-4">
              <AppointmentsTable
                rows={sorted}
                session={session}
                sort={sort}
                onSortChange={setSort}
                vobStatusById={vobStatusById}
                onRowClick={setSelectedId}
                showLocation={showLocation}
                pageResetKey={pageResetKey}
              />
            </TabsContent>

            <TabsContent value="calendar" className="mt-4">
              <AppointmentsCalendar rows={sorted} session={session} onRowClick={setSelectedId} />
            </TabsContent>
          </Tabs>
        </div>
          )}
        </>
      )}

      {selected ? (
        <AppointmentDrawer
          appointment={selected}
          vobRecord={selected.vobId ? vobById.get(selected.vobId) ?? null : null}
          session={session}
          flagged={flagged.has(selected.id)}
          onStatusChange={handleStatusChange}
          onAddNote={handleAddNote}
          onFlag={handleFlag}
          onClose={() => setSelectedId(null)}
        />
      ) : null}
    </div>
  );
}

