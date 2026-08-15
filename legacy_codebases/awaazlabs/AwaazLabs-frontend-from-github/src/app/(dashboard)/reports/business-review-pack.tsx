'use client';

/**
 * §16.1 — "Monthly business review pack: a one-click generated deck-style PDF combining
 * outcomes, quality trend, and revenue-recovered estimate; built for the clinic to show its
 * own stakeholders."
 *
 * WHY NOT A REAL PDF: there is no PDF library in this build and none may be added. Faking a
 * download would produce a broken file. Instead this is a print-ready on-page summary with a
 * "Print / Save as PDF" button that calls `window.print()`, plus a `@media print` rule that
 * hides the app chrome and prints only the pack. That is honest and actually works — the OS
 * print dialog's "Save as PDF" gives the clinic the deliverable.
 *
 * The revenue-recovered estimate and aggregate quality score are read from `@/lib/metrics`
 * (`revenueRecoveredEstimate`, `aggregateQualityScore`) — the same functions Overview and
 * Quality use — so the numbers cannot drift from those tabs.
 */

import React, { useMemo } from 'react';
import { Building2, DollarSign, Printer, TrendingUp } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Sparkline } from '@/components/charts/sparkline';
import { formatCount, formatDateTime, formatPercent, formatUsd, timezoneFor } from '@/lib/format';
import {
  aggregateQualityScore,
  appointmentStats,
  qualityTrend,
  revenueRecoveredEstimate,
  scopeToLocation,
  vobCounts,
} from '@/lib/metrics';
import { getFixture } from '@/mock/fixtures';
import { getLocationById, mockNow } from '@/mock/orgs';
import { useSession } from '@/shared/session-context';
import { Button } from '@/components/ui/button';

/** Print scoping: hide the app shell, print only the pack. No color declared here. */
const PRINT_CSS = `
@media print {
  body * { visibility: hidden !important; }
  #brp-print-root, #brp-print-root * { visibility: visible !important; }
  #brp-print-root { position: absolute; left: 0; top: 0; width: 100%; }
  .brp-no-print { display: none !important; }
}
`;

function pct(value: number | null): string {
  return value === null ? '—' : formatPercent(value);
}

interface Metric {
  readonly label: string;
  readonly value: string;
}

function MetricGrid({ metrics }: { metrics: readonly Metric[] }): React.JSX.Element {
  return (
    <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {metrics.map((m) => (
        <div key={m.label} className="rounded-md border border-border p-4">
          <dt className="text-sm text-muted-foreground">{m.label}</dt>
          <dd className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{m.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function BusinessReviewPack(): React.JSX.Element {
  const { session, org } = useSession();
  const fixture = getFixture(session.orgId);

  const appts = useMemo(() => appointmentStats(fixture, session), [fixture, session]);
  const vob = useMemo(() => vobCounts(fixture, session), [fixture, session]);
  const revenue = useMemo(() => revenueRecoveredEstimate(fixture, org, session), [fixture, org, session]);

  const scopedCalls = useMemo(() => scopeToLocation(fixture.calls, session), [fixture, session]);
  const qualityScore = useMemo(() => aggregateQualityScore(scopedCalls), [scopedCalls]);
  const trend = useMemo(() => qualityTrend(scopedCalls, 30), [scopedCalls]);
  const trendDelta = trend.length >= 2 ? Math.round((trend[trend.length - 1] - trend[0]) * 10) / 10 : 0;

  const now = mockNow();
  const primaryTz = org.locations[0] ? org.locations[0].timezone : 'UTC';
  const generatedAt = formatDateTime(now.toISOString(), timezoneFor(session.orgId, org.locations[0]?.id ?? ''));
  const periodLabel = new Intl.DateTimeFormat('en-US', {
    timeZone: primaryTz,
    month: 'long',
    year: 'numeric',
  }).format(now);
  const scopeLabel =
    session.locationId === null
      ? 'All locations'
      : getLocationById(session.orgId, session.locationId)?.name ?? session.locationId;

  const outcomeMetrics: Metric[] = [
    { label: 'Appointments booked (this week)', value: formatCount(appts.bookedThisWeek) },
    { label: 'Booking rate', value: pct(appts.bookingRateThisWeek) },
    { label: 'Confirmation rate', value: pct(appts.confirmationRate) },
    {
      label: 'No-show rate (30 days)',
      value: org.outcomeDataAvailable ? pct(appts.noShowRate30d) : 'Not tracked',
    },
    { label: 'VOB verified rate (this week)', value: pct(vob.verifiedRateThisWeek) },
    { label: 'Verifications needing attention', value: formatCount(vob.worklistNeedsAttention) },
  ];

  return (
    <div className="flex flex-col gap-4">
      <style>{PRINT_CSS}</style>

      <div className="brp-no-print flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          A print-ready summary. Use your browser&apos;s print dialog and choose &ldquo;Save as
          PDF&rdquo; to produce a file for stakeholders.
        </p>
        <Button onClick={() => window.print()} aria-label="Print or save the business review pack as PDF">
          <Printer className="mr-2 h-4 w-4" aria-hidden="true" />
          Print / Save as PDF
        </Button>
      </div>

      <div id="brp-print-root" className="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
              {org.name} — Monthly business review
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              {periodLabel} · {scopeLabel} · Generated {generatedAt}
            </p>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Outcomes</CardTitle>
          </CardHeader>
          <CardContent>
            <MetricGrid metrics={outcomeMetrics} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              Quality trend (30 days)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {qualityScore === null ? (
              <p className="text-sm text-muted-foreground">No graded calls in the current scope yet.</p>
            ) : (
              <div className="flex flex-wrap items-end gap-8">
                <div>
                  <p className="text-sm text-muted-foreground">Current aggregate score</p>
                  <p className="text-3xl font-semibold tabular-nums text-foreground">{qualityScore}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">30-day change</p>
                  <p className="text-3xl font-semibold tabular-nums text-foreground">
                    {trendDelta > 0 ? '+' : ''}
                    {trendDelta}
                  </p>
                </div>
                <div className="min-w-[160px] flex-1">
                  <Sparkline values={trend} ariaLabel={`Quality score over the last 30 days, currently ${qualityScore}`} />
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <DollarSign className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              Revenue recovered (estimate)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {revenue === null ? (
              <p className="text-sm text-muted-foreground">
                Average appointment value is not configured for this organization, so the
                revenue-recovered estimate is unavailable (it would otherwise read a misleading $0).
              </p>
            ) : (
              <div className="flex flex-col gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Estimated revenue recovered this month</p>
                  <p className="text-4xl font-semibold tabular-nums text-foreground">
                    {formatUsd(revenue.totalUsd)}
                  </p>
                </div>
                <MetricGrid
                  metrics={[
                    { label: 'After-hours bookings', value: formatCount(revenue.afterHoursBookings) },
                    { label: 'Reengagement bookings', value: formatCount(revenue.reengagementBookings) },
                    { label: 'Recovered no-shows', value: formatCount(revenue.recoveredNoShows) },
                    { label: 'Average appointment value', value: formatUsd(revenue.avgAppointmentValueUsd) },
                  ]}
                />
                <p className="text-xs text-muted-foreground">
                  (after-hours bookings + reengagement bookings + recovered no-shows) ×
                  average appointment value.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
