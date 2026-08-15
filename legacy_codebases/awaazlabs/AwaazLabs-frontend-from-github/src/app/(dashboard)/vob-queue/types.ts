/**
 * Local view-model types for the §8 VOB Queue worklist.
 *
 * These describe optimistic UI state (row action results) and a per-row display model that
 * the table and the CSV export share, so a cell and its exported value can never disagree.
 * Nothing here re-declares a canonical status — statuses come from `@/shared/status-models`.
 */

import type { AgingLevel } from '@/lib/metrics';
import type { VobRecordView } from '@/mock/data-access';
import type { VobResolveReason, VobStatus } from '@/shared/status-models';

/** One entry in the displayed status timeline (§8.3 "updates the status timeline"). */
export interface DisplayTimelineEntry {
  readonly at: string;
  readonly status: VobStatus;
  readonly actor: string;
  /** Optional human note attached by a row action (retry reason, resolution, escalation). */
  readonly note?: string;
}

/**
 * Optimistic per-row overrides. The fixture is read-only (guide: timestamps never drift),
 * so a row action mutates only this local map, never the record.
 */
export interface VobOverride {
  /** New effective status after Retry / etc. `undefined` = unchanged. */
  readonly status?: VobStatus;
  /** Reassignment from Escalate. `undefined` = unchanged. */
  readonly assignedTo?: string | null;
  /** Set true by Mark resolved; the row leaves the active worklist. */
  readonly resolved?: boolean;
  readonly resolvedReason?: VobResolveReason;
  readonly extraTimeline: readonly DisplayTimelineEntry[];
  readonly extraNotes: readonly { readonly at: string; readonly body: string }[];
}

/** The four §8.3 row actions. Each maps to a `recordVobQueueAction` audit event. */
export type VobRowAction = 'retry' | 'resolve' | 'escalate' | 'add_note';

/**
 * One display row, computed once in the client from the projected record + overrides, then
 * consumed identically by the table and the exporter. `phoneMasked` is the ONLY phone value
 * that ever leaves the projection here — the raw number is never read (§8.4 export guard).
 */
export interface VobRowVM {
  readonly record: VobRecordView;
  readonly effectiveStatus: VobStatus;
  readonly effectiveAssignedTo: string | null;
  readonly patientName: string;
  readonly phoneMasked: string;
  /** Formatted in the row's location timezone, or '—' when there is no linked appointment. */
  readonly linkedApptDate: string;
  readonly ageHours: number;
  readonly ageLabel: string;
  readonly agingLevel: AgingLevel;
  readonly lastAttempt: string;
  readonly attemptsCount: number;
  readonly locationName: string;
  readonly timezone: string;
}
