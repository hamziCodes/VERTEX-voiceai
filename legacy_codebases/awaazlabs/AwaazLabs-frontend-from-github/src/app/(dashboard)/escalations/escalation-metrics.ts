/**
 * §11.3 stat-strip metrics and the §11.2 aging rule, computed from the escalation set.
 *
 * The past-threshold rule is the SAME rule the Overview attention banner uses
 * (`attentionConditions` in `src/lib/metrics.ts`): open, and older than
 * `ESCALATION_ACK_THRESHOLD_MINUTES.urgent` (Urgent) or `.default` (everything else).
 * The threshold minutes are never hardcoded — they come from `status-models.ts`.
 */

import { hoursSince, isThisWeek } from '@/lib/metrics';
import { ratio } from '@/lib/format';
import {
  ESCALATION_ACK_THRESHOLD_MINUTES,
  ESCALATION_TRIGGERS,
  type EscalationStatus,
  type EscalationTrigger,
} from '@/shared/status-models';

/** The effective, override-aware shape the metrics operate on. */
export interface EscalationLike {
  readonly atUtc: string;
  readonly trigger: EscalationTrigger;
  readonly status: EscalationStatus;
  readonly acknowledgedAtUtc: string | null;
}

/** §11.2 "default 30 minutes for Urgent, 4 hours otherwise" — read from the enum, never inlined. */
export function ackThresholdMinutes(trigger: EscalationTrigger): number {
  return trigger === 'triage_urgent_emergency'
    ? ESCALATION_ACK_THRESHOLD_MINUTES.urgent
    : ESCALATION_ACK_THRESHOLD_MINUTES.default;
}

/** §11.2 aging rule, identical to `attentionConditions`' escalation branch. */
export function isPastThreshold(e: EscalationLike): boolean {
  if (e.status !== 'open') return false;
  return hoursSince(e.atUtc) * 60 > ackThresholdMinutes(e.trigger);
}

function median(values: readonly number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export interface EscalationStats {
  readonly total: number;
  /** §11.3 "Escalations this week". */
  readonly thisWeek: number;
  /** §11.3 "acknowledgement rate" = acknowledged (or resolved) / total. Null when total is 0. */
  readonly ackRate: number | null;
  /** §11.3 "median time to acknowledge", in seconds. Null when nothing is acknowledged. */
  readonly medianTimeToAckSeconds: number | null;
  /** §11.3 "breakdown by trigger" — count per trigger, in canonical order. */
  readonly triggerCounts: Readonly<Record<EscalationTrigger, number>>;
}

export function computeEscalationStats(escalations: readonly EscalationLike[]): EscalationStats {
  const acknowledged = escalations.filter((e) => e.acknowledgedAtUtc !== null);

  const ackDeltaMinutes = acknowledged.map(
    (e) => (new Date(e.acknowledgedAtUtc as string).getTime() - new Date(e.atUtc).getTime()) / 60000,
  );
  const medianMinutes = median(ackDeltaMinutes);

  const triggerCounts = Object.fromEntries(
    ESCALATION_TRIGGERS.map((t) => [t, escalations.filter((e) => e.trigger === t).length]),
  ) as Record<EscalationTrigger, number>;

  return {
    total: escalations.length,
    thisWeek: escalations.filter((e) => isThisWeek(e.atUtc)).length,
    ackRate: ratio(acknowledged.length, escalations.length),
    medianTimeToAckSeconds: medianMinutes === null ? null : medianMinutes * 60,
    triggerCounts,
  };
}
