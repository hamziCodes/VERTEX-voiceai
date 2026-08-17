'use client';

/**
 * §11 ESCALATIONS — every safety escalation and clinical-question routing in one
 * accountable surface.
 *
 * Escalations are read straight from `fixture.escalations` (there is no `listEscalations`
 * projection); the PHI gate is therefore applied here by branching on
 * `canSeePatientRows(session)`, mirroring the §10.4 precedent: in NON-PHI mode the stat
 * strip and an aggregate count render, but the patient-level table is hidden.
 *
 * Acknowledgement (§11.2) is gated on `canAcknowledgeEscalation` — a Viewer sees no
 * acknowledge control. Acknowledging updates optimistic local state (the fixture is
 * read-only). Appending an outcome note writes the truthful `note_edit` audit event; the
 * bare acknowledgement writes none, because §2.3 has no `escalation_acknowledged` type and
 * no thirteenth type is invented (see the drawer and the audit file).
 *
 * Statuses, triggers, labels, and the acknowledgement thresholds all import from
 * `@/shared/status-models`; none is re-declared here.
 */

import React, { useCallback, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ShieldAlert } from 'lucide-react';

import { Banner } from '@/components/ui/banner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { formatCount, formatDateTime, timezoneFor } from '@/lib/format';
import { hoursSince } from '@/lib/metrics';
import { useLiveEscalations, useLiveNotifications } from '@/hooks/use-dashboard-live';
import {
  acknowledgeLiveEscalation,
  saveLiveEscalationNote,
  type LiveEscalation,
} from '@/lib/dashboard-live';
import { canAcknowledgeEscalation, canExport, canSeePatientRows } from '@/mock/data-access';
import { getLocationById, mockNow } from '@/mock/orgs';
import { ESCALATION_TRIGGER_LABELS, ESCALATION_TRIGGERS, ESCALATION_STATUSES, ESCALATION_STATUS_LABELS, type EscalationStatus } from '@/shared/status-models';
import { useSession } from '@/shared/session-context';
import { buildEscalationsCsv } from '@/app/(dashboard)/reports/csv';
import { filtersToParams, runCsvExport } from '@/lib/csv-export';

import { computeEscalationStats, isPastThreshold, type EscalationLike } from './escalation-metrics';
import { EscalationDetailDrawer } from './escalation-detail-drawer';
import { ExportCsvButton, ListExportRow } from '@/components/ui/export-csv-button';
import { EscalationsFilters, ALL_FILTER_VALUE } from './escalations-filters';
import { EscalationsStatStrip } from './escalations-stat-strip';
import { EscalationsTable } from './escalations-table';
import type { EscalationOverride, EscalationRowVM } from './types';

const HEADER = (
  <PageHeader
    title="Escalations"
    description="Every safety escalation and clinical-question routing in one accountable surface — the safety audit trail, and live proof the clinical boundary holds."
  />
);

export function EscalationsClient(): React.JSX.Element {
  const { session, org, showLocationFilter } = useSession();
  const searchParams = useSearchParams();
  const statusFromUrl = searchParams.get('status');
  const initialStatus =
    statusFromUrl === 'pending'
      ? 'pending'
      : statusFromUrl !== null && (ESCALATION_STATUSES as readonly string[]).includes(statusFromUrl)
        ? statusFromUrl
        : ALL_FILTER_VALUE;

  const { data: live, isLoading: loadingLive, error: liveError, invalidate } = useLiveEscalations();
  const { invalidate: invalidateNotifications } = useLiveNotifications();
  const [overrides, setOverrides] = useState<Readonly<Record<string, EscalationOverride>>>({});
  const [status, setStatus] = useState<string>(initialStatus);
  const [trigger, setTrigger] = useState<string>(ALL_FILTER_VALUE);
  const [location, setLocation] = useState<string>(ALL_FILTER_VALUE);
  const [openRowId, setOpenRowId] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const canAck = canAcknowledgeEscalation(session);
  const canExportRows = canExport(session);
  const scoped = useMemo<readonly LiveEscalation[]>(
    () => (live?.gated.kind === 'rows' ? live.gated.rows : []),
    [live],
  );

  // Effective (override-aware) escalation shape drives the stat strip in every mode.
  const effectiveOf = useCallback(
    (e: LiveEscalation): EscalationLike => {
      const record = e.record;
      const ov = overrides[record.id];
      const acknowledgedAtUtc = ov?.acknowledgedAtUtc ?? record.acknowledgedAtUtc;
      const effectiveStatus: EscalationStatus =
        acknowledgedAtUtc !== null && record.status === 'open' ? 'acknowledged' : record.status;
      return { atUtc: record.atUtc, trigger: record.trigger, status: effectiveStatus, acknowledgedAtUtc };
    },
    [overrides],
  );

  const stats = useMemo(() => {
    const fallback = computeEscalationStats(scoped.map(effectiveOf));
    if (!live?.stats) return fallback;
    return {
      ...live.stats,
      triggerCounts: Object.fromEntries(
        ESCALATION_TRIGGERS.map((t) => [t, live.stats.triggerCounts[t] ?? 0]),
      ) as typeof fallback.triggerCounts,
    };
  }, [live?.stats, scoped, effectiveOf]);

  const vms = useMemo<EscalationRowVM[]>(() => {
    return scoped.map((e) => {
      const record = e.record;
      const ov = overrides[record.id];
      const acknowledgedAtUtc = ov?.acknowledgedAtUtc ?? record.acknowledgedAtUtc;
      const acknowledgedBy = ov?.acknowledgedBy ?? record.acknowledgedBy;
      const resolutionNote = ov?.resolutionNote ?? record.resolutionNote;
      const effectiveStatus: EscalationStatus =
        acknowledgedAtUtc !== null && record.status === 'open' ? 'acknowledged' : record.status;
      const tz = timezoneFor(session.orgId, record.locationId);
      return {
        record,
        patientName: e.patientName,
        source: record.sourceInteractionId
          ? { kind: 'call', href: `/conversations/calls?interaction=${record.sourceInteractionId}` }
          : null,
        triggerLabel: ESCALATION_TRIGGER_LABELS[record.trigger],
        effectiveStatus,
        acknowledgedAtUtc,
        acknowledgedBy,
        resolutionNote,
        locationName: e.locationName ?? getLocationById(session.orgId, record.locationId)?.name ?? record.locationId,
        timezone: tz,
        timestampLabel: formatDateTime(record.atUtc, tz),
        ackTimestampLabel: acknowledgedAtUtc ? formatDateTime(acknowledgedAtUtc, tz) : null,
        ageHours: hoursSince(record.atUtc),
        pastThreshold: isPastThreshold({ atUtc: record.atUtc, trigger: record.trigger, status: effectiveStatus, acknowledgedAtUtc }),
      };
    });
  }, [scoped, overrides, session.orgId]);

  const filtered = useMemo(
    () =>
      vms.filter((vm) => {
        if (status === 'pending' && vm.record.status === 'resolved') return false;
        if (status !== ALL_FILTER_VALUE && status !== 'pending' && vm.effectiveStatus !== status) return false;
        if (trigger !== ALL_FILTER_VALUE && vm.record.trigger !== trigger) return false;
        if (location !== ALL_FILTER_VALUE && vm.record.locationId !== location) return false;
        return true;
      }),
    [vms, status, trigger, location],
  );

  const exportFilterParams = useMemo(
    () =>
      filtersToParams({
        status: status === ALL_FILTER_VALUE ? 'all' : status,
        trigger: trigger === ALL_FILTER_VALUE ? 'all' : trigger,
        location: location === ALL_FILTER_VALUE ? 'all' : location,
      }),
    [status, trigger, location],
  );

  const handleExport = useCallback(() => {
    const rows = filtered.map((vm) => ({
      patientName: vm.patientName,
      triggerLabel: vm.triggerLabel,
      statusLabel: ESCALATION_STATUS_LABELS[vm.effectiveStatus],
      routedTo: vm.record.routedTo ?? '',
      acknowledgedAt: vm.ackTimestampLabel ?? '',
      acknowledgedBy: vm.acknowledgedBy ?? '',
      createdAt: vm.timestampLabel,
      locationName: vm.locationName,
    }));
    const error = runCsvExport(
      session,
      'escalations',
      filtered.length,
      exportFilterParams,
      `escalations-${new Date().toISOString().slice(0, 10)}.csv`,
      buildEscalationsCsv(rows),
    );
    setExportError(error);
  }, [session, filtered, exportFilterParams]);

  const now = () => mockNow().toISOString();

  // §11.2 one-tap acknowledge. Optimistic; NO audit event (no truthful §2.3 type exists).
  const handleAcknowledge = useCallback(
    (id: string) => {
      if (!canAck) return;
      setOverrides((prev) => ({
        ...prev,
        [id]: { ...prev[id], acknowledgedAtUtc: now(), acknowledgedBy: session.actor },
      }));
      void acknowledgeLiveEscalation(session, id)
        .then(() => {
          invalidate();
          invalidateNotifications();
        })
        .catch(() => undefined);
    },
    [canAck, invalidate, invalidateNotifications, session],
  );

  // §11.2 append an outcome note. Writes the truthful `note_edit` audit event (refuses for
  // a Viewer, structurally). Acknowledges too if still open, since a handled escalation is
  // by definition owned.
  const handleSaveNote = useCallback(
    (id: string, note: string) => {
      void saveLiveEscalationNote(session, id, note)
        .then(() => {
          invalidate();
          invalidateNotifications();
        })
        .catch(() => undefined);
      setOverrides((prev) => {
        const cur = prev[id] ?? {};
        const acknowledgedAtUtc = cur.acknowledgedAtUtc ?? now();
        const acknowledgedBy = cur.acknowledgedBy ?? session.actor;
        return { ...prev, [id]: { ...cur, resolutionNote: note, acknowledgedAtUtc, acknowledgedBy } };
      });
      setOpenRowId(null);
    },
    [invalidate, invalidateNotifications, session],
  );

  // Cedar (escalations: []) and any fully-scoped-out location land here — never a crash.
  if (loadingLive && !live) {
    return (
      <div className="flex flex-col gap-6">
        {HEADER}
        <Banner variant="default" title="Loading live escalations">
          Pulling the latest Retell-backed escalations from Supabase.
        </Banner>
      </div>
    );
  }

  if (liveError) {
    return (
      <div className="flex flex-col gap-6">
        {HEADER}
        <Banner variant="destructive" title="Live escalation data unavailable">
          {liveError}
        </Banner>
      </div>
    );
  }

  if (live?.gated.kind === 'aggregate') {
    return (
      <div className="flex flex-col gap-6">
        {HEADER}
        <Banner variant="default" title="NON-PHI mode">
          Patient-level escalation rows are hidden in NON-PHI mode. Aggregate counts and the trigger
          breakdown remain available.
        </Banner>
        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle>Escalations in scope</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold tabular-nums text-foreground">{formatCount(live.gated.total)}</p>
            <p className="mt-1 text-sm text-muted-foreground">Aggregate count for the current scope.</p>
          </CardContent>
        </Card>
        <EscalationsStatStrip stats={stats} />
      </div>
    );
  }

  if (scoped.length === 0) {
    return (
      <div>
        {HEADER}
        <EmptyState
          icon={<ShieldAlert className="h-8 w-8" />}
          title="No escalations"
          description="When an agent hands a conversation to a human — triage, a clinical question, or a caller request — it appears here for acknowledgement and follow-up."
        />
      </div>
    );
  }

  // §11 / §10.4 NON-PHI degraded state: aggregate counts + stat strip, patient table hidden.
  if (!canSeePatientRows(session)) {
    return (
      <div className="flex flex-col gap-6">
        {HEADER}
        <Banner variant="default" title="NON-PHI mode">
          Patient-level escalation rows are hidden in NON-PHI mode. Aggregate counts and the trigger
          breakdown remain available.
        </Banner>
        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle>Escalations in scope</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold tabular-nums text-foreground">{formatCount(stats.total)}</p>
            <p className="mt-1 text-sm text-muted-foreground">Aggregate count for the current scope.</p>
          </CardContent>
        </Card>
        <EscalationsStatStrip stats={stats} />
      </div>
    );
  }

  const openRow = openRowId ? vms.find((v) => v.record.id === openRowId) ?? null : null;

  return (
    <div className="flex flex-col gap-6">
      {HEADER}

      {exportError ? (
        <Banner variant="destructive" title="Export failed" onDismiss={() => setExportError(null)}>
          {exportError}
        </Banner>
      ) : null}

      <EscalationsStatStrip stats={stats} />

      <Card>
        <CardHeader className="gap-4">
          <CardTitle className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            {formatCount(filtered.length)} escalation{filtered.length === 1 ? '' : 's'}
          </CardTitle>
          <EscalationsFilters
            status={status}
            trigger={trigger}
            location={location}
            locations={org.locations.map((l) => ({ id: l.id, name: l.name }))}
            showLocationFilter={showLocationFilter}
            onStatus={setStatus}
            onTrigger={setTrigger}
            onLocation={setLocation}
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
              icon={<ShieldAlert className="h-8 w-8" />}
              title="No escalations match these filters"
              description="Adjust the status, trigger, or location filters to see more."
            />
          ) : (
            <EscalationsTable
              rows={filtered}
              canAck={canAck}
              onAcknowledge={handleAcknowledge}
              onOpenRow={setOpenRowId}
            />
          )}
        </CardContent>
      </Card>

      {openRow ? (
        <EscalationDetailDrawer
          row={openRow}
          open={openRowId !== null}
          onOpenChange={(o) => setOpenRowId(o ? openRow.record.id : null)}
          canAck={canAck}
          onAcknowledge={handleAcknowledge}
          onSaveNote={handleSaveNote}
        />
      ) : null}
    </div>
  );
}
