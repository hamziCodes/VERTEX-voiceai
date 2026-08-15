'use client';

/**
 * §4.1 Section A — Appointments. Four stat cards + a bookings-over-time chart.
 *
 * Every headline number comes from `appointmentStats` (metrics.ts). The no-show card hides
 * entirely when the org has no outcome data (§4.1, BUILD_NOTES B9) rather than showing a
 * misleading zero. The chart is stacked by the three §4.1 chart sources with a 7D/30D
 * toggle; its data and its honest `tableData` are built from the same buckets.
 */

import React, { useState } from 'react';
import { StatCard } from '@/components/ui/stat-card';
import { StatGridSkeleton } from '@/components/ui/skeleton';
import { BarChart } from '@/components/charts/bar-chart';
import { SOURCE_SERIES } from '@/components/charts/series-map';
import { APPOINTMENT_SOURCE_LABELS, BOOKING_CHART_SOURCES } from '@/shared/status-models';
import { formatCount, formatPercent } from '@/lib/format';
import type { AppointmentStats } from '@/lib/metrics';
import type { OverviewBookingPoint } from '../lib';
import { bookingsBySource, trailingDayLabels } from '../lib';
import { RangeTabs, type RangeDays } from '../range-tabs';

function pct(value: number | null): string {
  return value === null ? '—' : formatPercent(value);
}

export function AppointmentsSection({
  stats,
  appointments,
  outcomeDataAvailable,
  loading = false,
}: {
  stats: AppointmentStats;
  appointments: readonly OverviewBookingPoint[];
  outcomeDataAvailable: boolean;
  loading?: boolean;
}): React.JSX.Element {
  const [days, setDays] = useState<RangeDays>(7);

  const todayDelta = stats.bookedToday - stats.bookedSameWeekdayLastWeek;

  const xLabels = trailingDayLabels(days);
  const bySource = bookingsBySource(appointments, days);
  const series = BOOKING_CHART_SOURCES.map((source) => ({
    key: source,
    label: APPOINTMENT_SOURCE_LABELS[source],
    color: SOURCE_SERIES[source],
    values: bySource.find((s) => s.source === source)?.values ?? [],
  }));

  const tableRows = xLabels.map((label, i) => {
    const perSource = series.map((s) => s.values[i] ?? 0);
    const total = perSource.reduce((a, b) => a + b, 0);
    return [label, ...perSource.map((v) => formatCount(v)), formatCount(total)];
  });

  return (
    <section aria-labelledby="overview-appointments">
      <h2 id="overview-appointments" className="pb-3 text-lg font-semibold tracking-tight text-foreground">
        Appointments
      </h2>

      {loading ? (
        <StatGridSkeleton cards={outcomeDataAvailable ? 4 : 3} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Booked today"
          value={stats.bookedToday}
          format="number"
          href="/appointments"
          delta={{
            value: todayDelta,
            direction: todayDelta >= 0 ? 'up' : 'down',
            caption: 'vs same weekday last week',
          }}
          deltaIsGood={todayDelta >= 0}
        />

        <StatCard
          label="Booked this week"
          value={stats.bookedThisWeek}
          format="number"
          href="/appointments"
          subStats={[{ label: 'Booking rate', value: pct(stats.bookingRateThisWeek) }]}
        />

        <StatCard
          label="Upcoming next 7 days"
          value={stats.upcomingNext7Days}
          format="number"
          href="/appointments?filter=upcoming"
          linkLabel="View upcoming appointments"
        />

        {outcomeDataAvailable ? (
          <StatCard
            label="No-shows & cancellations this week"
            value={stats.noShowsAndCancellationsThisWeek}
            format="number"
            href="/appointments"
            subStats={[{ label: 'Rate', value: pct(stats.noShowCancelRateThisWeek) }]}
          />
        ) : null}
        </div>
      )}

      <div className="mt-4 flex flex-col gap-2">
        <div className="flex justify-end">
          <RangeTabs value={days} onChange={setDays} label="Bookings time range" />
        </div>
        <BarChart
          title="Bookings over time"
          description={`Trailing ${days} days, stacked by source`}
          variant="stacked"
          xLabels={xLabels}
          series={series}
          formatValue={(v) => formatCount(v)}
          showStackTotals={days === 7}
          tableData={{
            columns: ['Day', ...series.map((s) => s.label), 'Total'],
            rows: tableRows,
          }}
          footnote="Form bookings are excluded from this chart per §4.1; they appear in the Appointments source column."
        />
      </div>
    </section>
  );
}
