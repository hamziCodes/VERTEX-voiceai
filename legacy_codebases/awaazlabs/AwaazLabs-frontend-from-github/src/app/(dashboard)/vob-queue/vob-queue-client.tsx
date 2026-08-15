'use client';

/**
 * §8 VOB QUEUE — the actionable, exception-driven verification worklist.
 *
 * Data comes from the live dashboard API (`?resource=vob_queue`), a discriminated union:
 * in NON-PHI mode it returns `{ kind: 'aggregate' }` and the table is hidden (only counts
 * render); in PHI mode it returns rows. Statuses import from `@/shared/status-models`
 * (§7.3 canonical model) — no status string is re-declared here.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ClipboardList, Filter, ShieldAlert, X } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { useLiveAppointments, useLiveCalls, useLiveNotifications, useLiveVobQueue } from '@/hooks/use-dashboard-live';
import { formatAge, formatCount, formatDate, formatDateTime } from '@/lib/format';
import { timezoneFor } from '@/lib/format';
import { agingLevel, hoursSince } from '@/lib/metrics';
import {
  addLiveVobNote,
  escalateLiveVob,
  resolveLiveVob,
  retryLiveVob,
} from '@/lib/dashboard-live';
import { getLocationById } from '@/mock/orgs';
import {
  canExport,
  canPerformWorkflowActions,
  PermissionDeniedError,
  recordExport,
  recordVobQueueAction,
  type CallInteractionView,
  type VobRecordView,
} from '@/mock/data-access';
import {
  isVobNeedsAttention,
  VOB_AGING_THRESHOLD_HOURS,
  VOB_RESOLVE_REASON_LABELS,
  VOB_STATUSES,
  type VobResolveReason,
  type VobStatus,
} from '@/shared/status-models';
import { useSession } from '@/shared/session-context';

import { VobDetailDrawer } from './vob-detail-drawer';
import { ExportCsvButton, ListExportRow } from '@/components/ui/export-csv-button';
import { VobFilters, ALL_FILTER_VALUE, type AgeFilter } from './vob-filters';
import { VobWorklistTable } from './vob-worklist-table';
import { buildVobCsv, downloadCsv } from './vob-export';
import type { VobOverride, VobRowVM } from './types';

const EMPTY_OVERRIDE: VobOverride = { extraTimeline: [], extraNotes: [] };
const UNASSIGNED = '__unassigned__';

export function VobQueueClient() {
  const { session, showLocationFilter } = useSession();

  const searchParams = useSearchParams();
  const [needsAttentionOnly, setNeedsAttentionOnly] = useState(
    searchParams.get('filter') === 'needs-attention',
  );

  const [status, setStatus] = useState<string>(ALL_FILTER_VALUE);
  const [payer, setPayer] = useState<string>(ALL_FILTER_VALUE);
  const [age, setAge] = useState<AgeFilter>('all');
  const [assignedTo, setAssignedTo] = useState<string>(ALL_FILTER_VALUE);
  const [location, setLocation] = useState<string>(ALL_FILTER_VALUE);

  const [overrides, setOverrides] = useState<Readonly<Record<string, VobOverride>>>({});
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());
  const [openRowId, setOpenRowId] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: liveVob, isLoading, error: liveError, invalidate } = useLiveVobQueue();
  const { invalidate: invalidateNotifications } = useLiveNotifications();
  const { data: liveCalls } = useLiveCalls();
  const { data: liveAppointments } = useLiveAppointments();

  const result = liveVob?.gated ?? { kind: 'aggregate' as const, total: 0, reason: 'NON_PHI_MODE' as const };
  const showLoading = isLoading && liveVob === null;

  const callById = useMemo(() => {
    const map = new Map<string, CallInteractionView>(liveVob?.embeddedCalls ?? []);
    if (liveCalls?.gated.kind === 'rows') {
      for (const call of liveCalls.gated.rows) map.set(call.id, call);
    }
    return map;
  }, [liveVob, liveCalls]);

  const resolveCall = useCallback((id: string) => callById.get(id), [callById]);

  const apptDateById = useMemo(() => {
    if (liveAppointments?.gated.kind !== 'rows') return new Map<string, string>();
    return new Map(liveAppointments.gated.rows.map((appointment) => [appointment.id, appointment.startsAtUtc]));
  }, [liveAppointments]);

  const canAct = canPerformWorkflowActions(session);
  const canExportRows = canExport(session);

  const rows = useMemo<readonly VobRecordView[]>(
    () => (result.kind === 'rows' ? result.rows : []),
    [result],
  );

  const allVms = useMemo<VobRowVM[]>(() => {
    return rows.map((record) => {
      const ov = overrides[record.id];
      const effectiveStatus = ov?.status ?? record.status;
      const effectiveAssignedTo =
        ov && 'assignedTo' in ov && ov.assignedTo !== undefined ? ov.assignedTo : record.assignedTo;
      const tz = timezoneFor(session.orgId, record.locationId);
      const ageHours = hoursSince(record.requestedAtUtc);
      const identity = record.contact.identity;
      return {
        record,
        effectiveStatus,
        effectiveAssignedTo,
        patientName: identity ? `${identity.firstName} ${identity.lastName}` : 'Unknown patient',
        phoneMasked: identity?.phoneMasked ?? '—',
        linkedApptDate:
          record.appointmentId && apptDateById.has(record.appointmentId)
            ? formatDate(apptDateById.get(record.appointmentId) as string, tz)
            : '—',
        ageHours,
        ageLabel: formatAge(ageHours),
        agingLevel: agingLevel({ ...record, status: effectiveStatus }),
        lastAttempt: record.lastAttemptAtUtc ? formatDateTime(record.lastAttemptAtUtc, tz) : '—',
        attemptsCount: record.attempts.length,
        locationName:
          record.locationName ??
          getLocationById(session.orgId, record.locationId)?.name ??
          record.locationId,
        timezone: tz,
      };
    });
  }, [rows, overrides, apptDateById, session.orgId]);

  const openRows = useMemo(
    () => allVms.filter((vm) => !vm.record.resolved && !overrides[vm.record.id]?.resolved),
    [allVms, overrides],
  );

  const locationOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const vm of allVms) {
      const id = vm.record.locationId;
      if (!id) continue;
      if (!map.has(id)) map.set(id, vm.locationName);
    }
    return [...map.entries()]
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [allVms]);

  const showLocationFilterBar = showLocationFilter && locationOptions.length > 1;

  const statusOptions = useMemo(() => {
    const present = new Set(openRows.map((vm) => vm.effectiveStatus));
    return VOB_STATUSES.filter((s) => present.has(s));
  }, [openRows]);

  const payers = useMemo(
    () => Array.from(new Set(openRows.map((v) => v.record.payer))).sort(),
    [openRows],
  );
  const assignees = useMemo(
    () =>
      Array.from(
        new Set(openRows.map((v) => v.effectiveAssignedTo).filter((a): a is string => a !== null)),
      ).sort(),
    [openRows],
  );

  useEffect(() => {
    if (status !== ALL_FILTER_VALUE && !statusOptions.includes(status as VobStatus)) {
      setStatus(ALL_FILTER_VALUE);
    }
  }, [status, statusOptions]);

  useEffect(() => {
    if (payer !== ALL_FILTER_VALUE && !payers.includes(payer)) {
      setPayer(ALL_FILTER_VALUE);
    }
  }, [payer, payers]);

  useEffect(() => {
    if (assignedTo !== ALL_FILTER_VALUE && assignedTo !== UNASSIGNED && !assignees.includes(assignedTo)) {
      setAssignedTo(ALL_FILTER_VALUE);
    }
  }, [assignedTo, assignees]);

  useEffect(() => {
    if (location !== ALL_FILTER_VALUE && !locationOptions.some((l) => l.id === location)) {
      setLocation(ALL_FILTER_VALUE);
    }
  }, [location, locationOptions]);

  const filtered = useMemo(() => {
    const amber = VOB_AGING_THRESHOLD_HOURS.amber;
    const red = VOB_AGING_THRESHOLD_HOURS.red;
    return openRows.filter((vm) => {
      // Default view matches the open worklist (hide verified unless explicitly filtered).
      if (status === ALL_FILTER_VALUE && vm.effectiveStatus === 'verified') return false;

      if (needsAttentionOnly && !isVobNeedsAttention(vm.effectiveStatus)) return false;
      if (status !== ALL_FILTER_VALUE && vm.effectiveStatus !== status) return false;
      if (payer !== ALL_FILTER_VALUE && vm.record.payer !== payer) return false;
      if (age === 'fresh' && !(vm.ageHours < amber)) return false;
      if (age === 'amber' && !(vm.ageHours >= amber && vm.ageHours < red)) return false;
      if (age === 'red' && !(vm.ageHours >= red)) return false;
      if (assignedTo === UNASSIGNED && vm.effectiveAssignedTo !== null) return false;
      if (assignedTo !== ALL_FILTER_VALUE && assignedTo !== UNASSIGNED && vm.effectiveAssignedTo !== assignedTo)
        return false;
      if (location !== ALL_FILTER_VALUE && vm.record.locationId !== location) return false;
      return true;
    });
  }, [openRows, needsAttentionOnly, status, payer, age, assignedTo, location]);

  const now = () => new Date().toISOString();

  const applyOverride = useCallback((id: string, fn: (cur: VobOverride) => VobOverride) => {
    setOverrides((prev) => ({ ...prev, [id]: fn(prev[id] ?? EMPTY_OVERRIDE) }));
  }, []);

  const effectiveStatusOf = useCallback(
    (id: string) => {
      const rec = rows.find((r) => r.id === id);
      return overrides[id]?.status ?? rec?.status ?? 'queued';
    },
    [rows, overrides],
  );

  const handleRetry = useCallback(
    (id: string) => {
      try {
        recordVobQueueAction(session, id, 'retry');
      } catch (e) {
        if (!(e instanceof PermissionDeniedError)) throw e;
        return;
      }
      applyOverride(id, (cur) => ({
        ...cur,
        status: 'queued',
        resolved: false,
        extraTimeline: [
          ...cur.extraTimeline,
          { at: now(), status: 'queued', actor: session.actor, note: 'Re-queued for verification' },
        ],
      }));
      void retryLiveVob(session, id)
        .then(() => {
          invalidate();
          invalidateNotifications();
        })
        .catch(() => setActionError('Could not re-queue verification. Refresh and try again.'));
    },
    [session, applyOverride, invalidate, invalidateNotifications],
  );

  const handleResolve = useCallback(
    (id: string, reason: VobResolveReason) => {
      try {
        recordVobQueueAction(session, id, 'resolve', { reason });
      } catch (e) {
        if (!(e instanceof PermissionDeniedError)) throw e;
        return;
      }
      applyOverride(id, (cur) => ({
        ...cur,
        resolved: true,
        resolvedReason: reason,
        extraTimeline: [
          ...cur.extraTimeline,
          {
            at: now(),
            status: effectiveStatusOf(id),
            actor: session.actor,
            note: `Resolved: ${VOB_RESOLVE_REASON_LABELS[reason]}`,
          },
        ],
      }));
      setOpenRowId(null);
      void resolveLiveVob(session, id, reason)
        .then(() => {
          invalidate();
          invalidateNotifications();
        })
        .catch(() => setActionError('Could not resolve verification. Refresh and try again.'));
    },
    [session, applyOverride, effectiveStatusOf, invalidate, invalidateNotifications],
  );

  const handleEscalate = useCallback(
    (id: string, assignee: string) => {
      try {
        recordVobQueueAction(session, id, 'escalate', { assignee });
      } catch (e) {
        if (!(e instanceof PermissionDeniedError)) throw e;
        return;
      }
      applyOverride(id, (cur) => ({
        ...cur,
        assignedTo: assignee,
        extraTimeline: [
          ...cur.extraTimeline,
          {
            at: now(),
            status: effectiveStatusOf(id),
            actor: session.actor,
            note: `Escalated to ${assignee}`,
          },
        ],
      }));
      void escalateLiveVob(session, id, assignee)
        .then(() => {
          invalidate();
          invalidateNotifications();
        })
        .catch(() => setActionError('Could not escalate verification. Refresh and try again.'));
    },
    [session, applyOverride, effectiveStatusOf, invalidate, invalidateNotifications],
  );

  const handleAddNote = useCallback(
    (id: string, body: string) => {
      try {
        recordVobQueueAction(session, id, 'add_note');
      } catch (e) {
        if (!(e instanceof PermissionDeniedError)) throw e;
        return;
      }
      applyOverride(id, (cur) => ({
        ...cur,
        extraNotes: [...cur.extraNotes, { at: now(), body }],
        extraTimeline: [
          ...cur.extraTimeline,
          { at: now(), status: effectiveStatusOf(id), actor: session.actor, note: 'Note added' },
        ],
      }));
      void addLiveVobNote(session, id, body)
        .then(() => {
          invalidate();
          invalidateNotifications();
        })
        .catch(() => setActionError('Could not save note. Refresh and try again.'));
    },
    [session, applyOverride, effectiveStatusOf, invalidate, invalidateNotifications],
  );

  const toggle = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const filteredIds = useMemo(() => filtered.map((v) => v.record.id), [filtered]);
  const toggleAll = useCallback(() => {
    setSelectedIds((prev) => {
      const allSelected = filteredIds.length > 0 && filteredIds.every((id) => prev.has(id));
      if (allSelected) {
        const next = new Set(prev);
        filteredIds.forEach((id) => next.delete(id));
        return next;
      }
      return new Set([...prev, ...filteredIds]);
    });
  }, [filteredIds]);

  const handleBulkRetry = useCallback(() => {
    const ids = filteredIds.filter((id) => selectedIds.has(id));
    ids.forEach((id) => handleRetry(id));
    setSelectedIds(new Set());
  }, [filteredIds, selectedIds, handleRetry]);

  const filterParams = useMemo<Record<string, string>>(
    () => ({
      status: status === ALL_FILTER_VALUE ? 'all' : status,
      payer: payer === ALL_FILTER_VALUE ? 'all' : payer,
      age,
      assignedTo: assignedTo === ALL_FILTER_VALUE ? 'all' : assignedTo,
      location: location === ALL_FILTER_VALUE ? 'all' : location,
      needsAttentionOnly: String(needsAttentionOnly),
    }),
    [status, payer, age, assignedTo, location, needsAttentionOnly],
  );

  const pageResetKey = useMemo(() => JSON.stringify(filterParams), [filterParams]);

  const handleExport = useCallback(() => {
    try {
      recordExport(session, 'vob_queue', filtered.length, filterParams);
      downloadCsv(`vob-queue-${new Date().toISOString().slice(0, 10)}.csv`, buildVobCsv(filtered));
      setExportError(null);
    } catch (e) {
      setExportError(e instanceof PermissionDeniedError ? 'Export not permitted for this role.' : 'Export failed.');
    }
  }, [session, filtered, filterParams]);

  const openRow = openRowId ? allVms.find((v) => v.record.id === openRowId) ?? null : null;

  const header = (
    <PageHeader
      title="VOB Queue"
      description="Exception-driven verification worklist. Work aging and needs-attention verifications, following the Infinx / pVerify pattern."
    />
  );

  if (showLoading) {
    return (
      <div>
        {header}
        <Card className="mt-4">
          <CardContent className="py-10 text-center text-sm text-muted-foreground">Loading verifications…</CardContent>
        </Card>
      </div>
    );
  }

  if (result.kind === 'aggregate') {
    return (
      <div>
        {header}
        <Banner variant="default" title="NON-PHI mode">
          Patient-level rows are hidden in NON-PHI mode. The VOB Agent analytics tab remains fully
          available.
        </Banner>
        <Card className="mt-4 max-w-sm">
          <CardHeader>
            <CardTitle>Verifications in queue</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold tabular-nums text-foreground">{formatCount(result.total)}</p>
            <p className="mt-1 text-sm text-muted-foreground">Aggregate count for the current scope.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div>
      {header}

      {liveError ? (
        <Banner variant="destructive" className="mb-4">
          {liveError}
        </Banner>
      ) : null}

      {actionError ? (
        <Banner variant="destructive" className="mb-4" onDismiss={() => setActionError(null)}>
          {actionError}
        </Banner>
      ) : null}

      {needsAttentionOnly ? (
        <div className="mb-4 flex items-center gap-2">
          <Badge variant="destructive">
            <span className="inline-flex items-center gap-1">
              <ShieldAlert className="h-3 w-3" aria-hidden="true" />
              Needs attention only
            </span>
          </Badge>
          <Button variant="outline" size="sm" onClick={() => setNeedsAttentionOnly(false)}>
            <X className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
            Clear
          </Button>
        </div>
      ) : null}

      {exportError ? (
        <Banner variant="destructive" className="mb-4" onDismiss={() => setExportError(null)}>
          {exportError}
        </Banner>
      ) : null}

      <Card>
        <CardHeader className="gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              {formatCount(filtered.length)} verification{filtered.length === 1 ? '' : 's'}
            </CardTitle>
          </div>
          <VobFilters
            status={status}
            payer={payer}
            age={age}
            assignedTo={assignedTo}
            location={location}
            statuses={statusOptions}
            payers={payers}
            assignees={assignees}
            locations={locationOptions}
            showLocationFilter={showLocationFilterBar}
            onStatus={setStatus}
            onPayer={setPayer}
            onAge={setAge}
            onAssignedTo={setAssignedTo}
            onLocation={setLocation}
            selectedCount={filteredIds.filter((id) => selectedIds.has(id)).length}
            onBulkRetry={handleBulkRetry}
            canAct={canAct}
          />
          {canExportRows ? (
            <ListExportRow>
              <ExportCsvButton onClick={handleExport} disabled={filtered.length === 0} />
            </ListExportRow>
          ) : null}
        </CardHeader>
        <CardContent>
          {filtered.length === 0 ? (
            <EmptyState
              icon={<ClipboardList className="h-8 w-8" />}
              title="No verifications match these filters"
              description="Adjust the status, payer, age, assignee, or location filters to see more."
            />
          ) : (
            <VobWorklistTable
              rows={filtered}
              canAct={canAct}
              selectedIds={selectedIds}
              onToggle={toggle}
              onToggleAll={toggleAll}
              onOpenRow={setOpenRowId}
              pageResetKey={pageResetKey}
            />
          )}
        </CardContent>
      </Card>

      {openRow ? (
        <VobDetailDrawer
          row={openRow}
          override={overrides[openRow.record.id]}
          open={openRowId !== null}
          onOpenChange={(o) => setOpenRowId(o ? openRow.record.id : null)}
          session={session}
          canAct={canAct}
          resolveCall={resolveCall}
          onRetry={handleRetry}
          onResolve={handleResolve}
          onEscalate={handleEscalate}
          onAddNote={handleAddNote}
        />
      ) : null}
    </div>
  );
}
