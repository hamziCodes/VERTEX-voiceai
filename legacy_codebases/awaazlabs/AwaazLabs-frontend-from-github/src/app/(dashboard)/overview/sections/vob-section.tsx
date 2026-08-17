'use client';

/**
 * §4.2 Section B — VOB status. Three stat cards + a compact status distribution bar.
 *
 * Card numbers come from `GET ?resource=vob_stats` (via `useLiveVobQueue`). The distribution
 * bar uses the same backend aggregate grouped by `vobStatusGroup`.
 */

import React from 'react';
import { StatCard } from '@/components/ui/stat-card';
import { StatGridSkeleton } from '@/components/ui/skeleton';
import { DistributionBar } from '@/components/charts/distribution-bar';
import {
  VOB_STATUS_GROUPS,
  VOB_STATUS_GROUP_LABELS,
  VOB_STATUS_GROUP_SERIES,
  type VobStatusGroup,
} from '@/components/charts/series-map';
import { VOB_STATUS_LABELS } from '@/shared/status-models';
import { formatCount, formatPercent } from '@/lib/format';
import type { VobCounts } from '@/lib/metrics';

export function VobSection({
  counts,
  distributionByGroup,
  loading = false,
}: {
  counts: VobCounts;
  distributionByGroup: Readonly<Record<VobStatusGroup, number>>;
  loading?: boolean;
}): React.JSX.Element {
  const segments = VOB_STATUS_GROUPS.map((group) => ({
    key: group,
    label: VOB_STATUS_GROUP_LABELS[group],
    value: distributionByGroup[group],
    color: VOB_STATUS_GROUP_SERIES[group],
  }));

  const verifiedRate = counts.verifiedRateThisWeek === null ? '—' : formatPercent(counts.verifiedRateThisWeek);

  return (
    <section aria-labelledby="overview-vob">
      <h2 id="overview-vob" className="pb-3 text-lg font-semibold tracking-tight text-foreground">
        VOB status
      </h2>

      {loading ? (
        <StatGridSkeleton cards={3} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="VOB in progress"
            value={counts.inProgress}
            format="number"
            href="/agents/vob"
            subStats={[
              { label: VOB_STATUS_LABELS.queued, value: formatCount(counts.inProgressBySubStatus.queued) },
              { label: VOB_STATUS_LABELS.dialing, value: formatCount(counts.inProgressBySubStatus.dialing) },
              { label: VOB_STATUS_LABELS.on_call, value: formatCount(counts.inProgressBySubStatus.on_call) },
              { label: VOB_STATUS_LABELS.pending_callback, value: formatCount(counts.inProgressBySubStatus.pending_callback) },
            ]}
          />

          <StatCard
            label="VOB completed this week"
            value={counts.completedThisWeek}
            format="number"
            href="/agents/vob"
            subStats={[
              { label: 'Completed today', value: formatCount(counts.completedToday) },
              { label: 'Verified rate', value: verifiedRate },
            ]}
          />

          <StatCard
            label="Needs attention"
            value={counts.worklistNeedsAttention}
            format="number"
            accent="destructive"
            href="/vob-queue?filter=needs-attention"
            linkLabel="View VOB queue items needing attention"
          />
        </div>
      )}

      <div className="mt-4">
        <DistributionBar
          title="VOB status distribution"
          description="Open verifications in scope, grouped by outcome"
          compact
          segments={segments}
          formatValue={(v) => formatCount(v)}
          tableData={{
            columns: ['Group', 'Count'],
            rows: segments.map((s) => [s.label, formatCount(s.value)]),
          }}
        />
      </div>
    </section>
  );
}
