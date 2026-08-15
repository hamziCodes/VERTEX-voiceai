'use client';

/**
 * §4.5 Section E — Operational telemetry.
 *
 * Headline numbers (calls today, minutes today, avg duration, avg cost, first-audio avg,
 * success rate, completion counts, live calls) all come from `telemetry` (metrics.ts). The
 * over-time series are Overview-local buckets (metrics.ts exposes no time series). Calls
 * over time and minutes over time are TWO SEPARATE LineCharts (never a dual axis, per
 * THEME_NOTES §8); first-audio response is a third LineChart carrying the 800 ms target
 * line. All three share one 7D/30D toggle.
 *
 * "Interactions row: per-agent counts plus Overall and All" — interpreted (narrowest
 * self-consistent reading, both scoped to the location filter per §2.4) as: one count per
 * agent (voice calls attributed to that agent; the Chat agent's count is chat sessions),
 * "Overall" = all voice calls (the sum of the voice-agent tiles), and "All" = every
 * interaction across all channels (voice + chat).
 */

import React, { useState } from 'react';
import { StatCard } from '@/components/ui/stat-card';
import { LineChart } from '@/components/charts/line-chart';
import { AGENT_IDS, AGENT_LABELS } from '@/shared/status-models';
import { formatCount, formatDuration, formatMs, formatPercent, formatUsdPrecise } from '@/lib/format';
import { FIRST_AUDIO_TARGET_MS, type Telemetry } from '@/lib/metrics';
import type { CallInteraction, ChatInteraction } from '@/mock/schema';
import type { GatedRows, Session } from '@/mock/data-access';
import type { CallInteractionView } from '@/mock/data-access';
import { LiveCallsPanel } from '@/components/live/live-calls-panel';
import { callsPerDay, firstAudioPerDay, minutesPerDay, trailingDayLabels } from '../lib';
import { RangeTabs, type RangeDays } from '../range-tabs';

const CONVERSATIONS_HREF = '/conversations/calls';

function InteractionTile({ label, value, emphasize }: { label: string; value: string; emphasize?: boolean }): React.JSX.Element {
  return (
    <div className={emphasize ? 'rounded-md border border-border bg-muted/40 p-3' : 'rounded-md border border-border p-3'}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold tabular-nums text-foreground">{value}</p>
    </div>
  );
}

export function TelemetrySection({
  tele,
  calls,
  chats,
  refreshedAtLabel,
  session,
  liveCalls,
}: {
  tele: Telemetry;
  calls: readonly CallInteraction[];
  chats: readonly ChatInteraction[];
  refreshedAtLabel: string;
  session: Session;
  liveCalls: GatedRows<CallInteractionView>;
}): React.JSX.Element {
  const [days, setDays] = useState<RangeDays>(7);

  const perAgent = AGENT_IDS.map((id) => ({
    id,
    label: AGENT_LABELS[id],
    count: id === 'chat' ? chats.length : calls.filter((c) => c.agent === id).length,
  }));
  const overall = calls.length; // all voice calls
  const all = calls.length + chats.length; // every interaction, both channels

  const xLabels = trailingDayLabels(days);
  const callsSeries = callsPerDay(calls, days);
  const minutesSeries = minutesPerDay(calls, days);
  const firstAudioSeries = firstAudioPerDay(calls, days);

  return (
    <section aria-labelledby="overview-telemetry">
      <h2 id="overview-telemetry" className="pb-3 text-lg font-semibold tracking-tight text-foreground">
        Operational telemetry
      </h2>

      {/* Interactions row — per agent, plus Overall and All */}
      <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
        <p className="pb-3 text-sm font-medium text-muted-foreground">Interactions by agent</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {perAgent.map((a) => (
            <InteractionTile key={a.id} label={a.label} value={formatCount(a.count)} />
          ))}
          <InteractionTile label="Overall (voice)" value={formatCount(overall)} emphasize />
          <InteractionTile label="All (all channels)" value={formatCount(all)} emphasize />
        </div>
      </div>

      {/* Volume + cost stat cards */}
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Calls today" value={tele.callsToday} format="number" href={CONVERSATIONS_HREF} />
        <StatCard label="Minutes today" value={tele.minutesToday} format="number" href={CONVERSATIONS_HREF} />
        <StatCard
          label="Average duration"
          value={tele.avgDurationSeconds === null ? '—' : formatDuration(tele.avgDurationSeconds)}
          format="text"
          href={CONVERSATIONS_HREF}
        />
        <StatCard
          label="Average cost per interaction"
          value={tele.avgCostPerInteractionUsd === null ? '—' : formatUsdPrecise(tele.avgCostPerInteractionUsd)}
          format="text"
          href={CONVERSATIONS_HREF}
        />
      </div>

      {/* Success rate + live calls */}
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatCard
          label="Success rate"
          value={tele.successRate === null ? '—' : formatPercent(tele.successRate)}
          format="text"
          href={CONVERSATIONS_HREF}
          subStats={[{ label: 'Completed / attempted', value: `${formatCount(tele.completedCount)} / ${formatCount(tele.attemptedCount)}` }]}
        />
        <LiveCallsPanel snapshot={liveCalls} session={session} title="Live calls now" refreshedAtLabel={refreshedAtLabel} />
      </div>

      {/* Over-time charts — one shared 7D/30D toggle, one y-axis each */}
      <div className="mt-4 flex justify-end">
        <RangeTabs value={days} onChange={setDays} label="Telemetry time range" />
      </div>

      <div className="mt-2 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <LineChart
          title="Calls over time"
          description={`Trailing ${days} days`}
          xLabels={xLabels}
          series={[{ key: 'calls', label: 'Calls', color: 'var(--chart-1)', values: callsSeries }]}
          formatValue={(v) => formatCount(v)}
          tableData={{ columns: ['Day', 'Calls'], rows: xLabels.map((l, i) => [l, formatCount(callsSeries[i] ?? 0)]) }}
        />
        <LineChart
          title="Minutes over time"
          description={`Trailing ${days} days`}
          xLabels={xLabels}
          series={[{ key: 'minutes', label: 'Minutes', color: 'var(--chart-1)', values: minutesSeries }]}
          formatValue={(v) => formatCount(v)}
          tableData={{ columns: ['Day', 'Minutes'], rows: xLabels.map((l, i) => [l, formatCount(minutesSeries[i] ?? 0)]) }}
        />
      </div>

      <div className="mt-4">
        <LineChart
          title="Average first-audio response"
          description={
            tele.avgFirstAudioResponseMs === null
              ? `Trailing ${days} days`
              : `Trailing ${days} days · overall average ${formatMs(tele.avgFirstAudioResponseMs)}`
          }
          xLabels={xLabels}
          series={[{ key: 'first_audio', label: 'First-audio response', color: 'var(--chart-1)', values: firstAudioSeries }]}
          targetLine={{ value: FIRST_AUDIO_TARGET_MS, label: `Target ${FIRST_AUDIO_TARGET_MS} ms` }}
          formatValue={(v) => formatMs(v)}
          tableData={{
            columns: ['Day', 'First-audio response'],
            rows: xLabels.map((l, i) => [l, firstAudioSeries[i] === null ? '—' : formatMs(firstAudioSeries[i] as number)]),
          }}
        />
      </div>
    </section>
  );
}
