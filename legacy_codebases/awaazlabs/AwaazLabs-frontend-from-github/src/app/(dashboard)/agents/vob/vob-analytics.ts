/**
 * §7 VOB Agent analytics — pure derivations over VOB records.
 *
 * These read `VobRecord` fields only (payer, status, benefits, handle times) — no patient
 * identity — so the analytics tab survives NON-PHI mode. Statuses import from the canonical
 * §7.3 model; nothing is re-declared here.
 */

import { ratio } from '@/lib/format';
import { daysSince } from '@/lib/metrics';
import type { VobRecord } from '@/mock/schema';
import {
  isVobTerminal,
  VOB_TERMINAL_STATUSES,
  type VobTerminalStatus,
} from '@/shared/status-models';

const MS_PER_HOUR = 3_600_000;

/** The six terminal statuses shown as "percentage with count on hover" (§7.1). */
export const SHARE_STATUSES = [
  'partial_coverage',
  'needs_authorization',
  'needs_referral',
  'not_covered',
  'inactive_policy',
  'unable_to_verify',
] as const satisfies readonly VobTerminalStatus[];

export interface PeriodOption {
  readonly value: string;
  readonly label: string;
  /** Trailing days, or null for "all time". */
  readonly days: number | null;
}

export const PERIOD_OPTIONS: readonly PeriodOption[] = [
  { value: '7', label: 'Last 7 days', days: 7 },
  { value: '30', label: 'Last 30 days', days: 30 },
  { value: '90', label: 'Last 90 days', days: 90 },
  { value: 'all', label: 'All time', days: null },
];

export function filterByPeriod(records: readonly VobRecord[], days: number | null): readonly VobRecord[] {
  if (days === null) return records;
  return records.filter((r) => {
    const age = daysSince(r.requestedAtUtc);
    return age >= 0 && age <= days;
  });
}

function percentile(sortedAsc: readonly number[], p: number): number | null {
  if (sortedAsc.length === 0) return null;
  const idx = Math.min(sortedAsc.length - 1, Math.max(0, Math.round(p * (sortedAsc.length - 1))));
  return sortedAsc[idx];
}

export interface StatusShare {
  readonly count: number;
  readonly rate: number | null;
}

export interface BenefitCapture {
  readonly denom: number;
  readonly copay: number | null;
  readonly deductible: number | null;
  readonly outOfPocketMax: number | null;
}

export interface VobAnalytics {
  readonly verifications: number;
  readonly terminalCount: number;
  readonly verifiedRate: number | null;
  readonly statusShares: Readonly<Record<VobTerminalStatus, StatusShare>>;
  readonly priorAuthRate: number | null;
  readonly referralRate: number | null;
  readonly ivrSuccessRate: number | null;
  readonly benefitCapture: BenefitCapture;
  readonly memberNotFound: StatusShare;
  readonly payerRepsReached: number;
  readonly avgHandleSeconds: number | null;
  readonly turnaroundMedianHours: number | null;
  readonly turnaroundP95Hours: number | null;
}

export function computeVobAnalytics(records: readonly VobRecord[]): VobAnalytics {
  const terminal = records.filter((r) => isVobTerminal(r.status));
  const terminalCount = terminal.length;
  const withAttempts = records.filter((r) => r.attempts.length > 0);

  const statusShares = Object.fromEntries(
    VOB_TERMINAL_STATUSES.map((s) => {
      const count = terminal.filter((r) => r.status === s).length;
      return [s, { count, rate: ratio(count, terminalCount) }];
    }),
  ) as Record<VobTerminalStatus, StatusShare>;

  const allAttemptDurations = records.flatMap((r) => r.attempts.map((a) => a.durationSeconds));
  const avgHandleSeconds =
    allAttemptDurations.length > 0
      ? allAttemptDurations.reduce((a, b) => a + b, 0) / allAttemptDurations.length
      : null;

  const turnarounds = terminal
    .filter((r) => r.lastAttemptAtUtc !== null)
    .map((r) => (new Date(r.lastAttemptAtUtc as string).getTime() - new Date(r.requestedAtUtc).getTime()) / MS_PER_HOUR)
    .filter((h) => h >= 0)
    .sort((a, b) => a - b);

  return {
    verifications: records.length,
    terminalCount,
    verifiedRate: ratio(statusShares.verified.count, terminalCount),
    statusShares,
    priorAuthRate: ratio(terminal.filter((r) => r.priorAuthRequired).length, terminalCount),
    referralRate: ratio(terminal.filter((r) => r.referralRequired).length, terminalCount),
    ivrSuccessRate: ratio(
      withAttempts.filter((r) => r.ivrNavigationSucceeded).length,
      withAttempts.length,
    ),
    benefitCapture: {
      denom: terminalCount,
      copay: ratio(terminal.filter((r) => r.benefits.copayUsd !== null).length, terminalCount),
      deductible: ratio(terminal.filter((r) => r.benefits.deductibleUsd !== null).length, terminalCount),
      outOfPocketMax: ratio(
        terminal.filter((r) => r.benefits.outOfPocketMaxUsd !== null).length,
        terminalCount,
      ),
    },
    memberNotFound: statusShares.member_not_found,
    payerRepsReached: records.filter((r) => r.payerRepReached).length,
    avgHandleSeconds,
    turnaroundMedianHours: percentile(turnarounds, 0.5),
    turnaroundP95Hours: percentile(turnarounds, 0.95),
  };
}

/* ----------------------------------------------------------------------------------------
 * §7.2 verifications-over-time — weekly buckets over the trailing N weeks
 * -------------------------------------------------------------------------------------- */

export interface TimeSeries {
  readonly labels: readonly string[];
  readonly values: readonly number[];
}

/** Counts terminal verifications by completion week (`lastAttemptAtUtc`), oldest → newest. */
export function verificationsOverTime(records: readonly VobRecord[], weeks: number): TimeSeries {
  const buckets = new Array<number>(weeks).fill(0);
  for (const r of records) {
    if (!isVobTerminal(r.status) || r.lastAttemptAtUtc === null) continue;
    const age = daysSince(r.lastAttemptAtUtc);
    const weekIdx = Math.floor(age / 7);
    if (weekIdx < 0 || weekIdx >= weeks) continue;
    buckets[weeks - 1 - weekIdx] += 1;
  }
  const labels = Array.from({ length: weeks }, (_, i) => {
    const weeksAgo = weeks - 1 - i;
    return weeksAgo === 0 ? 'This week' : `${weeksAgo}w ago`;
  });
  return { labels, values: buckets };
}

/* ----------------------------------------------------------------------------------------
 * §7.2 payer breakdown — the surface a billing distributor evaluates first
 * -------------------------------------------------------------------------------------- */

export interface PayerRow {
  readonly payer: string;
  readonly verifications: number;
  readonly verifiedRate: number | null;
  readonly avgHandleSeconds: number | null;
  readonly unableToVerifyRate: number | null;
}

/** Grouped by payer, sorted by unable-to-verify rate DESC so problem payers surface first. */
export function payerBreakdown(records: readonly VobRecord[]): readonly PayerRow[] {
  const byPayer = new Map<string, VobRecord[]>();
  for (const r of records) {
    const list = byPayer.get(r.payer) ?? [];
    list.push(r);
    byPayer.set(r.payer, list);
  }

  const rows: PayerRow[] = [];
  for (const [payer, list] of byPayer) {
    const terminal = list.filter((r) => isVobTerminal(r.status));
    const durations = list.flatMap((r) => r.attempts.map((a) => a.durationSeconds));
    rows.push({
      payer,
      verifications: list.length,
      verifiedRate: ratio(terminal.filter((r) => r.status === 'verified').length, terminal.length),
      avgHandleSeconds: durations.length ? durations.reduce((a, b) => a + b, 0) / durations.length : null,
      unableToVerifyRate: ratio(terminal.filter((r) => r.status === 'unable_to_verify').length, terminal.length),
    });
  }

  return rows.sort((a, b) => (b.unableToVerifyRate ?? -1) - (a.unableToVerifyRate ?? -1));
}
