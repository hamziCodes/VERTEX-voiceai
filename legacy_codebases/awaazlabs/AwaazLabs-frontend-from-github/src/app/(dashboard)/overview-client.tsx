'use client';

/**
 * §4 Overview — the daily-glance page for the clinic owner and manager.
 *
 * Section order is the spec's product decision (§4): business outcomes first (Appointments,
 * VOB, Revenue, Quality), operational telemetry second. The attention banner (§4.6) renders
 * ABOVE Section A. Every stat card is a click-through to the tab that owns its data (§4).
 *
 * Overview is aggregate-only by nature, so it renders identically in PHI and NON-PHI mode —
 * no patient name, phone, recording, or transcript appears anywhere on this page in either mode.
 */

import React, { useMemo } from 'react';

import { PageHeader } from '@/components/ui/page-header';
import { LiveCallsPanel } from '@/components/live/live-calls-panel';
import { useLiveAppointments, useLiveCalls, useLiveVobQueue } from '@/hooks/use-dashboard-live';
import { mapDashboardStatsToAppointmentStats, mapVobStatsToCounts } from '@/lib/dashboard-live';
import { vobStatusGroup, type VobStatusGroup } from '@/components/charts/series-map';
import { formatDateTime, displayTimezone } from '@/lib/format';
import type { AppointmentStats, VobCounts } from '@/lib/metrics';
import { listCalls, type CallInteractionView, type GatedRows } from '@/mock/data-access';
import { getFixture } from '@/mock/fixtures';
import {
  aggregateQualityScore,
  optimizationEventsThisMonth,
  qualityTrend,
  revenueRecoveredEstimate,
  scopeToLocation,
  telemetry,
} from '@/lib/metrics';
import { useSession } from '@/shared/session-context';

import { AppointmentsSection } from './overview/sections/appointments-section';
import { VobSection } from './overview/sections/vob-section';
import { RevenueSection } from './overview/sections/revenue-section';
import { QualitySection } from './overview/sections/quality-section';
import { TelemetrySection } from './overview/sections/telemetry-section';
import { ExtractionSourceToggle } from './overview/extraction-source-toggle';

const EMPTY_VOB_COUNTS: VobCounts = {
  inProgress: 0,
  inProgressBySubStatus: { queued: 0, dialing: 0, on_call: 0, pending_callback: 0 },
  completedToday: 0,
  completedThisWeek: 0,
  verifiedRateThisWeek: null,
  overviewNeedsAttention: 0,
  worklistNeedsAttention: 0,
};

const EMPTY_VOB_DISTRIBUTION = { verified: 0, pending: 0, needs_attention: 0 } as const;

const EMPTY_APPT_STATS: AppointmentStats = {
  bookedToday: 0,
  bookedSameWeekdayLastWeek: 0,
  bookedThisWeek: 0,
  bookingRateThisWeek: null,
  upcomingNext7Days: 0,
  noShowsAndCancellationsThisWeek: 0,
  noShowCancelRateThisWeek: null,
  confirmationRate: null,
  noShowRate30d: null,
};

function liveCallsHref(snapshot: GatedRows<CallInteractionView>): string {
  if (snapshot.kind !== 'rows') return '/conversations/calls';
  const active = [...snapshot.rows]
    .filter((call) => call.disposition === 'in_progress')
    .sort((a, b) => new Date(b.atUtc).getTime() - new Date(a.atUtc).getTime())[0];
  return active ? `/conversations/calls?interaction=${active.id}` : '/conversations/calls';
}

export function OverviewClient(): React.JSX.Element {
  const { session, org } = useSession();
  const fixture = getFixture(session.orgId);

  const { data: liveAppointments, isLoading: liveApptLoading } = useLiveAppointments();
  const liveApptStats = useMemo(
    () => (liveAppointments ? mapDashboardStatsToAppointmentStats(liveAppointments.stats) : EMPTY_APPT_STATS),
    [liveAppointments],
  );
  const chartAppointments = useMemo(
    () =>
      liveAppointments?.gated.kind === 'rows'
        ? liveAppointments.gated.rows.map((row) => ({ bookedAtUtc: row.bookedAtUtc, source: row.source }))
        : [],
    [liveAppointments],
  );

  const { data: liveCallsSnapshot } = useLiveCalls();
  const fixtureCalls = useMemo(() => listCalls(fixture, session), [fixture, session]);
  const liveCalls = liveCallsSnapshot?.gated ?? fixtureCalls;

  const { data: liveVob, isLoading: liveVobLoading } = useLiveVobQueue();
  const liveVobCounts = useMemo(
    () => (liveVob ? mapVobStatsToCounts(liveVob.stats) : EMPTY_VOB_COUNTS),
    [liveVob],
  );
  const liveVobDistribution = useMemo(() => {
    if (liveVob?.gated.kind === 'rows') {
      const counts: Record<VobStatusGroup, number> = { verified: 0, pending: 0, needs_attention: 0 };
      for (const row of liveVob.gated.rows) {
        if (row.resolved) continue;
        counts[vobStatusGroup(row.status)] += 1;
      }
      return counts;
    }
    return liveVob?.stats.distributionByGroup ?? EMPTY_VOB_DISTRIBUTION;
  }, [liveVob]);

  const revenue = revenueRecoveredEstimate(fixture, org, session);
  const qualityScore = aggregateQualityScore(fixture.calls);
  const trend30d = qualityTrend(fixture.calls, 30);
  const optEvents = optimizationEventsThisMonth(fixture);
  const tele = telemetry(fixture, session);
  const scopedCalls = scopeToLocation(fixture.calls, session);
  const scopedChats = scopeToLocation(fixture.chats, session);
  const tz = displayTimezone(session, org);
  const refreshedAtLabel = formatDateTime(new Date().toISOString(), tz);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Overview" description="Daily glance across appointments, verification, quality, and operations." />

      <ExtractionSourceToggle />

      <LiveCallsPanel
        snapshot={liveCalls}
        session={session}
        title="Live calls now"
        refreshedAtLabel={refreshedAtLabel}
        cardHref={liveCallsHref(liveCalls)}
      />

      <AppointmentsSection
        stats={liveApptStats}
        appointments={chartAppointments}
        outcomeDataAvailable={org.outcomeDataAvailable}
        loading={liveApptLoading && liveAppointments === null}
      />

      <VobSection
        counts={liveVobCounts}
        distributionByGroup={liveVobDistribution}
        loading={liveVobLoading && liveVob === null}
      />

      <RevenueSection estimate={revenue} />

      <QualitySection score={qualityScore} trend30d={trend30d} optimizationEvents={optEvents} />

      <TelemetrySection
        tele={tele}
        calls={scopedCalls}
        chats={scopedChats}
        refreshedAtLabel={refreshedAtLabel}
        session={session}
        liveCalls={liveCalls}
      />
    </div>
  );
}
