'use client';

/**
 * §7 VOB AGENT TAB — eligibility & benefits verification analytics.
 *
 * Aggregate by nature (reads non-PHI record fields), so it survives NON-PHI mode. The
 * canonical §7.3 status model is imported; the same record shows the same chip here, on
 * Overview, in the VOB Queue, and in the Appointments table (all via `VobStatusChip`).
 */

import React, { useMemo, useState } from 'react';
import { ShieldCheck } from 'lucide-react';

import { EmptyState } from '@/components/ui/empty-state';
import { Select } from '@/components/ui/select';
import { StatCard } from '@/components/ui/stat-card';
import { AgentAnalyticsPage } from '@/components/agent-template/agent-analytics-page';
import { DistributionBar } from '@/components/charts/distribution-bar';
import { LineChart } from '@/components/charts/line-chart';
import {
  VOB_STATUS_GROUPS,
  VOB_STATUS_GROUP_LABELS,
  VOB_STATUS_GROUP_SERIES,
  vobStatusGroup,
  type VobStatusGroup,
} from '@/components/charts/series-map';
import { formatCount, formatDuration, formatPercent } from '@/lib/format';
import { formatAge } from '@/lib/format';
import { scopeToLocation } from '@/lib/metrics';
import { useLiveVobQueue } from '@/hooks/use-dashboard-live';
import { getFixture } from '@/mock/fixtures';
import type { VobRecord } from '@/mock/schema';
import { VOB_STATUSES, VOB_STATUS_LABELS } from '@/shared/status-models';
import { useSession } from '@/shared/session-context';

import { BenefitCaptureBars } from './benefit-capture-bars';
import { PayerBreakdownTable } from './payer-breakdown-table';
import {
  PERIOD_OPTIONS,
  SHARE_STATUSES,
  computeVobAnalytics,
  filterByPeriod,
  payerBreakdown,
  verificationsOverTime,
} from './vob-analytics';

const WEEKS = 8;

function pct(rate: number | null): string {
  return rate === null ? '—' : formatPercent(rate);
}

export function VobAgentClient() {
  const { session } = useSession();
  const fixture = getFixture(session.orgId);
  const { data: liveVob } = useLiveVobQueue();

  const [periodValue, setPeriodValue] = useState('90');
  const period = PERIOD_OPTIONS.find((p) => p.value === periodValue) ?? PERIOD_OPTIONS[2];

  const liveRecords = useMemo<readonly VobRecord[] | null>(() => {
    if (liveVob?.gated.kind !== 'rows') return null;
    return liveVob.gated.rows.filter((row) => !row.resolved);
  }, [liveVob]);

  const scoped = useMemo(() => {
    if (liveRecords) return liveRecords;
    return scopeToLocation(fixture.vobRecords, session);
  }, [liveRecords, fixture.vobRecords, session]);
  const periodRecords = useMemo(() => filterByPeriod(scoped, period.days), [scoped, period.days]);
  const a = useMemo(() => computeVobAnalytics(periodRecords), [periodRecords]);
  const payerRows = useMemo(() => payerBreakdown(periodRecords), [periodRecords]);
  const series = useMemo(() => verificationsOverTime(scoped, WEEKS), [scoped]);

  // §7.2 status distribution — three color-safe groups (THEME_NOTES series-map), summing to
  // 100%. The relief-channel table carries the full per-status breakdown.
  const groupCounts = useMemo(() => {
    const counts: Record<VobStatusGroup, number> = { verified: 0, pending: 0, needs_attention: 0 };
    for (const r of periodRecords) {
      if (r.resolved) continue;
      counts[vobStatusGroup(r.status)] += 1;
    }
    return counts;
  }, [periodRecords]);

  const distributionSegments = VOB_STATUS_GROUPS.map((g) => ({
    key: g,
    label: VOB_STATUS_GROUP_LABELS[g],
    value: groupCounts[g],
    color: VOB_STATUS_GROUP_SERIES[g],
  }));

  const perStatusRows = VOB_STATUSES.map((s) => ({
    label: VOB_STATUS_LABELS[s],
    count: periodRecords.filter((r) => !r.resolved && r.status === s).length,
  })).filter((r) => r.count > 0);

  /**
   * §2.6: "Every agent, standard or custom, renders from the same schema… and a standard
   * analytics page template (stat cards, one primary chart, one distribution component,
   * drill-through to interaction rows)."
   *
   * This tab predated the template and laid itself out by hand, which quietly made §2.6's
   * central claim false — an agent tab that does not use the shared template is proof the
   * shared template does not fit every agent. It now composes `AgentAnalyticsPage` like
   * every other agent surface.
   *
   * §7.1's three groupings collapse into the template's single stat grid. Nothing is lost:
   * the groupings were headings, not information, and each card already carries its own
   * tooltip. §7.2's benefit-capture sub-bars and payer breakdown table go in the `extra`
   * slot — the payer table keeps its own prominent heading, because §7.2 calls it "where a
   * billing company spots problem payers" and asks for it to be prominent.
   */
  return (
    <AgentAnalyticsPage
      agentName="VOB Agent"
      description="Eligibility and benefits verification performance. Analytics live here; the actionable worklist is the VOB Queue."
      specRef="§7"
      headerActions={
        <Select
          aria-label="Reporting period"
          value={periodValue}
          onValueChange={setPeriodValue}
          options={PERIOD_OPTIONS.map((p) => ({ value: p.value, label: p.label }))}
        />
      }
      isEmpty={periodRecords.length === 0}
      emptyState={
        <EmptyState
          title="No verifications in this period"
          description="Widen the reporting period to see analytics for this agent."
        />
      }
      /* §7.1 stat cards */
      stats={
        <>
          <StatCard label="Verifications" value={formatCount(a.verifications)} tooltip={period.label} />
          <StatCard label="Verified rate" value={pct(a.verifiedRate)} />
          {SHARE_STATUSES.map((s) => (
            <StatCard
              key={s}
              label={VOB_STATUS_LABELS[s]}
              value={pct(a.statusShares[s].rate)}
              tooltip={`${a.statusShares[s].count} of ${a.terminalCount} terminal verifications`}
            />
          ))}
          <StatCard
            label="Member not found"
            value={formatCount(a.memberNotFound.count)}
            subStats={[{ label: 'Share of terminal', value: pct(a.memberNotFound.rate) }]}
          />
          <StatCard
            label="Prior auth required"
            value={pct(a.priorAuthRate)}
            tooltip="Catching a prior-auth requirement pre-visit protects revenue that would otherwise be denied."
          />
          <StatCard label="Referral required" value={pct(a.referralRate)} />
          <StatCard label="IVR navigation success" value={pct(a.ivrSuccessRate)} />
          <StatCard label="Payer reps reached" value={formatCount(a.payerRepsReached)} />
          <StatCard
            label="Avg handle time per call"
            value={a.avgHandleSeconds === null ? '—' : formatDuration(a.avgHandleSeconds)}
            tooltip="Mean duration of a single payer call attempt."
          />
          <StatCard
            label="Turnaround (median)"
            value={a.turnaroundMedianHours === null ? '—' : formatAge(a.turnaroundMedianHours)}
            tooltip="Median time from request to a terminal status. Different from handle time — both matter."
          />
          <StatCard
            label="Turnaround (P95)"
            value={a.turnaroundP95Hours === null ? '—' : formatAge(a.turnaroundP95Hours)}
            tooltip="95th-percentile time from request to a terminal status."
          />
        </>
      }
      /* §2.6 slot: one primary chart */
      primaryChart={
        <LineChart
          title="Verifications over time"
          description="Terminal verifications completed per week."
          xLabels={series.labels}
          series={[{ key: 'verifications', label: 'Verifications', color: 'var(--chart-1)', values: [...series.values] }]}
          formatValue={(v) => formatCount(v)}
          tableData={{
            columns: ['Week', 'Verifications'],
            rows: series.labels.map((l, i) => [l, String(series.values[i])]),
          }}
        />
      }
      /* §2.6 slot: one distribution component (§7.2) */
      distribution={
        <DistributionBar
          title="VOB status distribution"
          description="Share of open verifications by outcome group. The data table carries the full per-status breakdown."
          segments={distributionSegments}
          formatValue={(v) => formatCount(v)}
          tableData={{
            columns: ['Status', 'Count'],
            rows: perStatusRows.map((r) => [r.label, String(r.count)]),
          }}
        />
      }
      /* §7.1 benefit-capture sub-bars, and §7.2's deliberately prominent payer table */
      extra={
        <div className="flex flex-col gap-8">
          <BenefitCaptureBars capture={a.benefitCapture} />
          <section className="flex flex-col gap-4">
            <h2 className="inline-flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
              <ShieldCheck className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
              Payer performance
            </h2>
            <PayerBreakdownTable rows={payerRows} />
          </section>
        </div>
      }
      /* §2.6 slot: drill-through to interaction rows */
      drillThrough={{ href: '/conversations/calls?agent=vob', label: 'View VOB calls in Conversations' }}
    />
  );
}
