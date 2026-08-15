'use client';

/**
 * §6 RECEPTIONIST TAB — inbound voice agent analytics.
 *
 * Renders through the §2.6 standard template (`AgentAnalyticsPage`): eight stat cards, one
 * primary chart (booking-rate trend), one distribution component (triage donut), the rest of
 * §6.2 in the template's `extra` slot, and the §6.3 drill-through into Conversations › Calls
 * scoped to this agent.
 *
 * Aggregate by nature — no patient name, phone, recording, or transcript is read — so it is
 * identical in PHI and NON-PHI mode.
 */

import React, { useMemo, useState } from 'react';

import { AgentAnalyticsPage } from '@/components/agent-template/agent-analytics-page';
import { EmptyState } from '@/components/ui/empty-state';
import { StatCard } from '@/components/ui/stat-card';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DonutChart } from '@/components/charts/donut-chart';
import { DistributionBar } from '@/components/charts/distribution-bar';
import { Heatmap } from '@/components/charts/heatmap';
import { LineChart } from '@/components/charts/line-chart';
import { TRIAGE_SERIES } from '@/components/charts/series-map';
import { formatCount, formatDuration, formatPercent } from '@/lib/format';
import { scopeToLocation } from '@/lib/metrics';
import { getFixture } from '@/mock/fixtures';
import { useSession } from '@/shared/session-context';
import {
  LANGUAGE_LABELS,
  TRIAGE_FLAG_LABELS,
} from '@/shared/status-models';

import {
  INTAKE_METHOD_LABELS,
  INTAKE_METHOD_SERIES,
  LANGUAGE_SERIES,
  bookingRateTrend,
  bookingsByHour,
  computeReceptionistStats,
  intakeDistribution,
  languageDistribution,
  receptionistBookings,
  receptionistCalls,
  triageDistribution,
} from './receptionist-analytics';

const DRILL_THROUGH = {
  href: '/conversations/calls?agent=receptionist',
  label: 'View Receptionist calls',
} as const;

/** Healthcare scheduling first-call-resolution benchmark referenced in §6.1. */
const FCR_BENCHMARK_LABEL = '≈75% (healthcare scheduling FCR benchmark)';

function pct(rate: number | null): string {
  return rate === null ? '—' : formatPercent(rate);
}

function SectionHeading({ children }: { children: React.ReactNode }): React.JSX.Element {
  return <h2 className="text-lg font-semibold tracking-tight text-foreground">{children}</h2>;
}

export function ReceptionistClient(): React.JSX.Element {
  const { session, org } = useSession();
  const fixture = getFixture(session.orgId);

  const appts = useMemo(
    () => scopeToLocation(fixture.appointments, session),
    [fixture.appointments, session],
  );
  const calls = useMemo(() => scopeToLocation(fixture.calls, session), [fixture.calls, session]);

  const stats = useMemo(() => computeReceptionistStats(appts, calls), [appts, calls]);

  const tzOf = useMemo(() => {
    const map = new Map(org.locations.map((l) => [l.id, l.timezone] as const));
    return (locationId: string): string => map.get(locationId) ?? 'UTC';
  }, [org.locations]);

  const triage = useMemo(() => triageDistribution(calls), [calls]);
  const intake = useMemo(() => intakeDistribution(appts), [appts]);
  const language = useMemo(() => languageDistribution(appts), [appts]);
  const heatmap = useMemo(() => bookingsByHour(appts, tzOf), [appts, tzOf]);

  const [trendDays, setTrendDays] = useState<'7' | '30'>('30');
  const trend = useMemo(
    () => bookingRateTrend(appts, calls, Number(trendDays)),
    [appts, calls, trendDays],
  );

  // §6.1 the tab is only truly empty when the agent has neither a booking nor a call in scope.
  const isEmpty = receptionistBookings(appts).length === 0 && receptionistCalls(calls).length === 0;

  const statCards = (
    <>
      <StatCard
        label="Appointments booked"
        value={formatCount(stats.bookings)}
        subStats={[{ label: 'Completed inbound calls', value: formatCount(stats.completedInboundCalls) }]}
        tooltip="Appointments booked by the Receptionist agent, shown against the completed inbound calls that produced them."
      />
      <StatCard
        label="Booking rate"
        value={pct(stats.bookingRate)}
        subStats={[{ label: 'Benchmark', value: FCR_BENCHMARK_LABEL }]}
        tooltip={`Booked / completed inbound calls. Healthcare scheduling first-call-resolution benchmarks land around 75%.`}
      />
      <StatCard
        label="Safety escalation rate"
        value={pct(stats.safetyEscalationRate)}
        tooltip="Share of Receptionist calls flagged triage High or Urgent. Triage is a four-level acuity model (None, Low, High, Urgent); High and Urgent route to a human for safety."
      />
      <StatCard
        label="Insurance capture rate"
        value={pct(stats.insuranceCaptureRate)}
        tooltip="Share of Receptionist bookings with insurance captured. Front-end capture reduces downstream claim denials."
      />
      <StatCard
        label="WhatsApp deflection-suitable"
        value={pct(stats.whatsappDeflectionRate)}
        tooltip="Share of completed inbound calls that were information-only — interactions a WhatsApp/text channel could have absorbed. Not actual WhatsApp volume."
      />
      <StatCard
        label="Avg booking handle time"
        value={stats.avgBookingHandleSeconds === null ? '—' : formatDuration(stats.avgBookingHandleSeconds)}
        tooltip="Mean duration of Receptionist calls that ended in a booking."
      />
      <StatCard
        label="After-hours share of bookings"
        value={pct(stats.afterHoursShare)}
        tooltip="Share of Receptionist bookings made outside configured business hours — the recovery story rendered as a metric."
      />
      <StatCard
        label="Missed & abandoned inbound"
        value={formatCount(stats.missedAndAbandoned)}
        accent={stats.missedAndAbandoned > 0 ? 'destructive' : 'default'}
        tooltip="Inbound legs that ended before the agent connected (abandoned or no answer). Target is near zero."
      />
    </>
  );

  const primaryChart = (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <SectionHeading>Booking rate trend</SectionHeading>
        <Tabs value={trendDays} onValueChange={(v) => setTrendDays(v === '7' ? '7' : '30')}>
          <TabsList label="Booking rate trend window">
            <TabsTrigger value="7">7D</TabsTrigger>
            <TabsTrigger value="30">30D</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
      <LineChart
        title={`Booking rate — last ${trendDays} days`}
        description="Bookings made ÷ completed inbound calls, per day. Days with no inbound calls have no rate and are drawn as a gap."
        xLabels={trend.labels}
        series={[
          {
            key: 'booking_rate',
            label: 'Booking rate',
            color: 'var(--chart-1)',
            values: [...trend.values],
          },
        ]}
        formatValue={(v) => `${v}%`}
        tableData={{
          columns: ['Day', 'Booking rate'],
          rows: trend.labels.map((l, i) => [l, trend.values[i] === null ? '—' : `${trend.values[i]}%`]),
        }}
      />
    </div>
  );

  const triageDonut = (
    <DonutChart
      title="Triage distribution"
      description="Acuity flags across all Receptionist calls. High and Urgent carry the reserved status colors."
      centerLabel="calls"
      slices={triage.map((t) => ({
        key: t.key,
        label: TRIAGE_FLAG_LABELS[t.key],
        value: t.count,
        color: TRIAGE_SERIES[t.key],
      }))}
      tableData={{
        columns: ['Triage', 'Calls'],
        rows: triage.map((t) => [TRIAGE_FLAG_LABELS[t.key], String(t.count)]),
      }}
    />
  );

  const extra = (
    <div className="flex flex-col gap-6">
      <div className="grid gap-6 xl:grid-cols-2">
        <DonutChart
          title="Intake method"
          description="How the Receptionist agent's bookings were captured."
          centerLabel="bookings"
          slices={intake.map((m) => ({
            key: m.key,
            label: INTAKE_METHOD_LABELS[m.key],
            value: m.count,
            color: INTAKE_METHOD_SERIES[m.key],
          }))}
          tableData={{
            columns: ['Intake method', 'Bookings'],
            rows: intake.map((m) => [INTAKE_METHOD_LABELS[m.key], String(m.count)]),
          }}
        />
        <DistributionBar
          title="Language mix"
          description="Language of Receptionist bookings (English, Spanish, other)."
          segments={language.map((l) => ({
            key: l.key,
            label: LANGUAGE_LABELS[l.key],
            value: l.count,
            color: LANGUAGE_SERIES[l.key],
          }))}
          formatValue={(v) => formatCount(v)}
          tableData={{
            columns: ['Language', 'Bookings'],
            rows: language.map((l) => [LANGUAGE_LABELS[l.key], String(l.count)]),
          }}
        />
      </div>
      <Heatmap
        title="Bookings by hour of day"
        description="When Receptionist bookings are made, in each location's local time. The two after-hours flanks are the recovery window."
        xLabels={heatmap.xLabels}
        yLabels={heatmap.yLabels}
        values={heatmap.values}
        columnGroups={heatmap.columnGroups}
        formatValue={(v) => formatCount(v)}
        tableData={{
          columns: ['Day', ...heatmap.xLabels],
          rows: heatmap.yLabels.map((day, r) => [day, ...heatmap.counts[r].map((c) => String(c))]),
        }}
      />
    </div>
  );

  return (
    <AgentAnalyticsPage
      agentName="Receptionist"
      description="Performance of the inbound voice agent: 24/7 call answering, appointment booking, triage with safety escalation, and intake capture."
      specRef="§6"
      stats={statCards}
      primaryChart={primaryChart}
      distribution={triageDonut}
      extra={extra}
      drillThrough={DRILL_THROUGH}
      isEmpty={isEmpty}
      emptyState={
        <EmptyState
          title="No Receptionist activity in scope"
          description="This location has no Receptionist calls or bookings yet. Analytics appear once the agent starts handling inbound calls."
        />
      }
    />
  );
}
