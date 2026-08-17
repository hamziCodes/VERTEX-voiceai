/**
 * §11 Escalations — view-model types and the trigger→color binding.
 *
 * The canonical enums (`EscalationStatus`, `EscalationTrigger`) are imported from
 * `@/shared/status-models`; nothing is re-declared here.
 */

import type { Escalation } from '@/mock/schema';
import type { EscalationStatus, EscalationTrigger } from '@/shared/status-models';

/** §11.2 optimistic acknowledgement state. The fixture is read-only, so a tap records here. */
export interface EscalationOverride {
  readonly acknowledgedAtUtc?: string;
  readonly acknowledgedBy?: string;
  readonly resolutionNote?: string;
}

/** One resolved source-interaction link (§11.1 "source interaction (call or chat link)"). */
export interface EscalationSourceLink {
  readonly kind: 'call' | 'chat';
  readonly href: string;
}

export interface EscalationRowVM {
  readonly record: Escalation;
  readonly patientName: string;
  readonly source: EscalationSourceLink | null;
  readonly triggerLabel: string;
  readonly effectiveStatus: EscalationStatus;
  readonly acknowledgedAtUtc: string | null;
  readonly acknowledgedBy: string | null;
  readonly resolutionNote: string | null;
  readonly locationName: string;
  readonly timezone: string;
  readonly timestampLabel: string;
  readonly ackTimestampLabel: string | null;
  readonly ageHours: number;
  /** §11.2 aging indicator: open past its configured acknowledgement threshold. */
  readonly pastThreshold: boolean;
}

/**
 * Trigger → categorical color, one fixed binding assigned once in `ESCALATION_TRIGGERS`
 * order (never cycled), so color follows the entity and filtering never repaints survivors
 * (THEME_NOTES §3).
 *
 * THEME_NOTES/SKILL says entity→color bindings live in
 * `src/components/charts/series-map.ts`. That file is FROZEN (read-only for this task) and
 * carries no escalation-trigger binding, so the binding is centralized here instead of being
 * inlined at the chart call site — the same guarantee the rule protects. Triggers are a
 * categorical set of routing reasons (not an ordinal good/bad severity), so they take
 * categorical `--chart-*` tokens, mirroring how §9.2's chat metrics (incl. "escalation")
 * are treated in series-map. Values are `var(--…)` token references — no literal color.
 */
export const TRIGGER_SERIES: Readonly<Record<EscalationTrigger, string>> = {
  triage_high: 'var(--chart-1)',
  triage_urgent_emergency: 'var(--chart-2)',
  clinical_question: 'var(--chart-3)',
  caller_requested_human: 'var(--chart-4)',
  agent_initiated: 'var(--chart-5)',
};
