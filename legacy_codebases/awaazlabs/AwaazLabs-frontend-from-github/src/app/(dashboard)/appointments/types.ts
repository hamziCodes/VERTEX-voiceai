/**
 * Appointments tab — shared client-side types and pure helpers. Spec §5.
 *
 * FILTER + SORT state live here so the table (§5.2/§5.3) and the calendar view (§5.5)
 * consume the same filtered, sorted rows. No color, no `any`, no status string literals —
 * every status/label comes from `@/shared/status-models`.
 */

import type {
  AppointmentSource,
  AppointmentStatus,
  Language,
  TriageFlag,
  VobStatus,
} from '@/shared/status-models';

/** §5.3 filter set. `'all'` = unfiltered; `'none'` on `vob` = appointment with no VOB record. */
export interface AppointmentFilters {
  /** §5.3 "free-text search on name and phone". */
  readonly search: string;
  readonly status: AppointmentStatus | 'all';
  readonly source: AppointmentSource | 'all';
  readonly vob: VobStatus | 'none' | 'all';
  readonly triage: TriageFlag | 'all';
  readonly language: Language | 'all';
  /** Location id, or `'all'`. Only surfaced when the org is multi-location (§2.4). */
  readonly locationId: string | 'all';
  /** yyyy-mm-dd, inclusive lower bound on the appointment's local date. '' = open. */
  readonly dateFrom: string;
  /** yyyy-mm-dd, inclusive upper bound. '' = open. */
  readonly dateTo: string;
}

export const DEFAULT_FILTERS: AppointmentFilters = {
  search: '',
  status: 'all',
  source: 'all',
  vob: 'all',
  triage: 'all',
  language: 'all',
  locationId: 'all',
  dateFrom: '',
  dateTo: '',
};

/** Sortable columns. */
export type SortKey = 'booked' | 'datetime' | 'name' | 'status' | 'triage';

export interface SortState {
  readonly key: SortKey;
  readonly dir: 'asc' | 'desc';
}

/** Default table order: next appointment to handle first. */
export const DEFAULT_SORT: SortState = { key: 'datetime', dir: 'asc' };

/** Severity order for sorting the triage column (None < Low < High < Urgent). */
export const TRIAGE_ORDER: Readonly<Record<TriageFlag, number>> = {
  none: 0,
  low: 1,
  high: 2,
  urgent: 3,
};

/**
 * Calendar date key (yyyy-mm-dd) in a given IANA timezone. Used only for grouping and
 * range comparison in the agenda (§5.5) and the date-range filter — never for display,
 * which always goes through `@/lib/format`. `en-CA` yields ISO-ordered y-m-d.
 */
export function localDateKey(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(iso));
}

/** A run of `count` consecutive yyyy-mm-dd keys (UTC) starting at `anchor`. */
export function dateKeyWindow(anchor: Date, count: number): readonly string[] {
  const keys: string[] = [];
  for (let i = 0; i < count; i += 1) {
    const d = new Date(anchor.getTime() + i * 86_400_000);
    keys.push(
      new Intl.DateTimeFormat('en-CA', {
        timeZone: 'UTC',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }).format(d),
    );
  }
  return keys;
}
