/**
 * §6 RECEPTIONIST — pure derivations over appointments and calls, scoped to the
 * Receptionist agent.
 *
 * These read only aggregate / non-identity fields (source, triage, disposition, timestamps,
 * afterHours, insuranceCaptured, language), so the tab survives NON-PHI mode. Every enum and
 * label imports from the canonical `@/shared/status-models`; nothing is re-declared. Every
 * rate goes through `ratio()`, which returns `null` (rendered as "—") rather than NaN or a
 * misleading 0% when its denominator is zero — the guard the near-empty Cedar org exercises.
 *
 * Color bindings for the two categorical dimensions that have no entry in the frozen
 * `series-map.ts` (intake method, patient language) live here as single module-level lookups
 * keyed by entity — the "color follows the entity, never its rank / never inline" rule
 * (THEME_NOTES §3). They reference only approved tokens; no literal color appears.
 */

import { mockNow } from '@/mock/orgs';
import { ratio } from '@/lib/format';
import { daysSince } from '@/lib/metrics';
import type { Appointment, CallInteraction } from '@/mock/schema';
import {
  LANGUAGES,
  TRIAGE_FLAGS,
  type AppointmentSource,
  type Language,
  type TriageFlag,
} from '@/shared/status-models';

const DAY_MS = 86_400_000;

/* ----------------------------------------------------------------------------------------
 * Scoping to the Receptionist agent
 * -------------------------------------------------------------------------------------- */

/** §6: the inbound voice agent. Its bookings are appointments it booked. */
export function receptionistBookings(appointments: readonly Appointment[]): readonly Appointment[] {
  return appointments.filter((a) => a.bookedByAgent === 'receptionist');
}

export function receptionistCalls(calls: readonly CallInteraction[]): readonly CallInteraction[] {
  return calls.filter((c) => c.agent === 'receptionist');
}

/**
 * §6.1 denominator: "completed inbound calls". A call that ended before the agent connected
 * (abandoned / no answer) is not a completed interaction.
 */
export function completedInboundReceptionistCalls(
  calls: readonly CallInteraction[],
): readonly CallInteraction[] {
  return receptionistCalls(calls).filter(
    (c) => c.direction === 'inbound' && c.disposition !== 'abandoned' && c.disposition !== 'no_answer',
  );
}

/* ----------------------------------------------------------------------------------------
 * §6.1 stat cards
 * -------------------------------------------------------------------------------------- */

export interface ReceptionistStats {
  readonly bookings: number;
  /** §6.1 "completed inbound calls denominator" — shown alongside the count. */
  readonly completedInboundCalls: number;
  readonly bookingRate: number | null;
  /** §6.1 triage High + Urgent share of Receptionist calls. */
  readonly safetyEscalationRate: number | null;
  readonly insuranceCaptureRate: number | null;
  readonly whatsappDeflectionRate: number | null;
  readonly avgBookingHandleSeconds: number | null;
  readonly afterHoursShare: number | null;
  /** §6.1 inbound legs that ended before agent connect; target near zero. */
  readonly missedAndAbandoned: number;
}

export function computeReceptionistStats(
  appointments: readonly Appointment[],
  calls: readonly CallInteraction[],
): ReceptionistStats {
  const bookings = receptionistBookings(appointments);
  const allCalls = receptionistCalls(calls);
  const completedInbound = completedInboundReceptionistCalls(calls);

  const bookedCalls = allCalls.filter((c) => c.disposition === 'booked');
  const bookedHandleSeconds = bookedCalls.reduce((sum, c) => sum + c.durationSeconds, 0);

  const highOrUrgent = allCalls.filter((c) => c.triage === 'high' || c.triage === 'urgent');

  /**
   * Interpretation (narrowest): "WhatsApp deflection-suitable" = completed inbound calls
   * whose only purpose was information (disposition `info_only`). Those are exactly the
   * interactions a text channel could have absorbed. Definition is stated in the card
   * tooltip so the number is never mistaken for actual WhatsApp volume.
   */
  const deflectionSuitable = completedInbound.filter((c) => c.disposition === 'info_only');

  const missedAndAbandoned = receptionistCalls(calls).filter(
    (c) => c.direction === 'inbound' && (c.disposition === 'abandoned' || c.disposition === 'no_answer'),
  ).length;

  return {
    bookings: bookings.length,
    completedInboundCalls: completedInbound.length,
    bookingRate: ratio(bookings.length, completedInbound.length),
    safetyEscalationRate: ratio(highOrUrgent.length, allCalls.length),
    insuranceCaptureRate: ratio(bookings.filter((a) => a.insuranceCaptured).length, bookings.length),
    whatsappDeflectionRate: ratio(deflectionSuitable.length, completedInbound.length),
    avgBookingHandleSeconds: bookedCalls.length > 0 ? bookedHandleSeconds / bookedCalls.length : null,
    afterHoursShare: ratio(bookings.filter((a) => a.afterHours).length, bookings.length),
    missedAndAbandoned,
  };
}

/* ----------------------------------------------------------------------------------------
 * §6.2 triage distribution donut — colors from the canonical TRIAGE_SERIES (series-map)
 * -------------------------------------------------------------------------------------- */

export interface CategoryCount<K extends string> {
  readonly key: K;
  readonly count: number;
}

export function triageDistribution(calls: readonly CallInteraction[]): readonly CategoryCount<TriageFlag>[] {
  const scoped = receptionistCalls(calls);
  return TRIAGE_FLAGS.map((flag) => ({
    key: flag,
    count: scoped.filter((c) => c.triage === flag).length,
  }));
}

/* ----------------------------------------------------------------------------------------
 * §6.2 intake-method donut (Form, Voice, Unknown)
 * -------------------------------------------------------------------------------------- */

export const INTAKE_METHODS = ['voice', 'form', 'unknown'] as const;
export type IntakeMethod = (typeof INTAKE_METHODS)[number];

export const INTAKE_METHOD_LABELS: Readonly<Record<IntakeMethod, string>> = {
  voice: 'Voice',
  form: 'Form',
  unknown: 'Unknown',
};

/** Local color binding (not in the frozen series-map). Token references only. */
export const INTAKE_METHOD_SERIES: Readonly<Record<IntakeMethod, string>> = {
  voice: 'var(--chart-1)',
  form: 'var(--chart-4)',
  unknown: 'hsl(var(--muted-foreground))',
};

function intakeMethodOf(source: AppointmentSource): IntakeMethod {
  if (source === 'voice') return 'voice';
  if (source === 'form') return 'form';
  return 'unknown';
}

export function intakeDistribution(
  appointments: readonly Appointment[],
): readonly CategoryCount<IntakeMethod>[] {
  const bookings = receptionistBookings(appointments);
  return INTAKE_METHODS.map((method) => ({
    key: method,
    count: bookings.filter((a) => intakeMethodOf(a.source) === method).length,
  }));
}

/* ----------------------------------------------------------------------------------------
 * §6.2 language mix (en, es, other)
 * -------------------------------------------------------------------------------------- */

/** Local color binding (not in the frozen series-map). Token references only. */
export const LANGUAGE_SERIES: Readonly<Record<Language, string>> = {
  en: 'var(--chart-1)',
  es: 'var(--chart-5)',
  other: 'hsl(var(--muted-foreground))',
};

export function languageDistribution(
  appointments: readonly Appointment[],
): readonly CategoryCount<Language>[] {
  const bookings = receptionistBookings(appointments);
  return LANGUAGES.map((lang) => ({
    key: lang,
    count: bookings.filter((a) => a.language === lang).length,
  }));
}

/* ----------------------------------------------------------------------------------------
 * §6.2 bookings-by-hour heatmap, split business hours vs after hours
 * -------------------------------------------------------------------------------------- */

/** Local wall-clock hour (0–23) for a UTC instant, in the given IANA zone. */
function localHour(iso: string, timeZone: string): number {
  const h = new Intl.DateTimeFormat('en-US', { timeZone, hour12: false, hour: '2-digit' }).format(
    new Date(iso),
  );
  const n = Number(h);
  return n === 24 ? 0 : n;
}

const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as const;

function localDayOfWeek(iso: string, timeZone: string): number {
  const wd = new Intl.DateTimeFormat('en-US', { timeZone, weekday: 'short' }).format(new Date(iso));
  return WEEKDAY_LABELS.indexOf(wd as (typeof WEEKDAY_LABELS)[number]);
}

const HOUR_START = 6;
const HOUR_END = 20;

function formatHourLabel(hour: number): string {
  if (hour === 0) return '12a';
  if (hour === 12) return '12p';
  return hour < 12 ? `${hour}a` : `${hour - 12}p`;
}

export interface BookingHeatmap {
  readonly xLabels: readonly string[];
  readonly yLabels: readonly string[];
  /** `values[day][hourIndex]`; `null` where no booking was made (kept off the color scale). */
  readonly values: ReadonlyArray<ReadonlyArray<number | null>>;
  /** Whole counts (0 included) for the relief-channel table. */
  readonly counts: ReadonlyArray<ReadonlyArray<number>>;
  readonly columnGroups: readonly { label: string; startCol: number; endCol: number }[];
}

/**
 * Bookings bucketed by the local weekday and hour at which they were made (`bookedAtUtc`).
 * "After hours" = made before the clinic opened (before 08:00) or after it closed (from
 * 17:00) — the recovery window §6.1 renders as a metric, here shown as geography.
 */
export function bookingsByHour(
  appointments: readonly Appointment[],
  tzOf: (locationId: string) => string,
): BookingHeatmap {
  const hours = HOUR_END - HOUR_START + 1;
  const counts: number[][] = WEEKDAY_LABELS.map(() => new Array<number>(hours).fill(0));

  for (const a of receptionistBookings(appointments)) {
    const tz = tzOf(a.locationId);
    const hour = localHour(a.bookedAtUtc, tz);
    if (hour < HOUR_START || hour > HOUR_END) continue;
    const dow = localDayOfWeek(a.bookedAtUtc, tz);
    if (dow < 0) continue;
    counts[dow][hour - HOUR_START] += 1;
  }

  const values = counts.map((row) => row.map((c) => (c === 0 ? null : c)));
  const xLabels = Array.from({ length: hours }, (_, i) => formatHourLabel(HOUR_START + i));

  // hours: index 0 = 06, business = 08..16 (close 17:00), after = the two flanks.
  const businessStart = 8 - HOUR_START;
  const businessEnd = 16 - HOUR_START;
  const columnGroups = [
    { label: 'Before open', startCol: 0, endCol: businessStart - 1 },
    { label: 'Business hours', startCol: businessStart, endCol: businessEnd },
    { label: 'After close', startCol: businessEnd + 1, endCol: hours - 1 },
  ];

  return { xLabels, yLabels: [...WEEKDAY_LABELS], values, counts, columnGroups };
}

/* ----------------------------------------------------------------------------------------
 * §6.2 booking-rate trend, 7D / 30D
 * -------------------------------------------------------------------------------------- */

export interface RateTrend {
  readonly labels: readonly string[];
  /** Percentage points 0–100, or `null` on a day with no completed inbound calls (a gap). */
  readonly values: readonly (number | null)[];
}

/**
 * Daily booking rate = Receptionist bookings made that day / completed inbound Receptionist
 * calls that day. A day with no inbound calls has no denominator, so its point is `null`
 * (a gap) rather than a fabricated 0% — the same honesty `ratio()` enforces on the cards.
 */
export function bookingRateTrend(
  appointments: readonly Appointment[],
  calls: readonly CallInteraction[],
  days: number,
): RateTrend {
  const bookings = receptionistBookings(appointments);
  const inbound = completedInboundReceptionistCalls(calls);

  const numer = new Array<number>(days).fill(0);
  const denom = new Array<number>(days).fill(0);

  for (const a of bookings) {
    const age = Math.floor(daysSince(a.bookedAtUtc));
    if (age >= 0 && age < days) numer[days - 1 - age] += 1;
  }
  for (const c of inbound) {
    const age = Math.floor(daysSince(c.atUtc));
    if (age >= 0 && age < days) denom[days - 1 - age] += 1;
  }

  const nowMs = mockNow().getTime();
  const fmt = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'numeric', day: 'numeric' });
  const labels = Array.from({ length: days }, (_, i) => fmt.format(new Date(nowMs - (days - 1 - i) * DAY_MS)));

  const values = numer.map((n, i) => {
    const rate = ratio(n, denom[i]);
    return rate === null ? null : Math.round(rate * 100);
  });

  return { labels, values };
}
