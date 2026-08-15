/**
 * Overview-local time-series helpers.
 *
 * These derive the daily buckets the §4.1 bookings-over-time chart plots.
 * Headline stat numbers come from the dashboard API (`?resource=stats`).
 */

import type { AppointmentSource } from '@/shared/status-models';
import { BOOKING_CHART_SOURCES } from '@/shared/status-models';

const MS_PER_DAY = 86_400_000;

export interface OverviewBookingPoint {
  readonly bookedAtUtc: string;
  readonly source: AppointmentSource;
}

/** Short label for the bucket `daysAgo` days before `now`. */
function dayLabel(daysAgo: number, now: Date): string {
  const d = new Date(now.getTime() - daysAgo * MS_PER_DAY);
  return new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric' }).format(d);
}

/** Oldest-to-newest labels for a trailing `days`-day window ending today. */
export function trailingDayLabels(days: number, now = new Date()): readonly string[] {
  return Array.from({ length: days }, (_, i) => dayLabel(days - 1 - i, now));
}

/** Bucket index for an ISO timestamp within a trailing `days` window, or -1 if outside. */
function bucketIndex(iso: string, days: number, now: Date): number {
  const age = (now.getTime() - new Date(iso).getTime()) / MS_PER_DAY;
  if (age < 0 || age >= days) return -1;
  return days - 1 - Math.floor(age);
}

export interface SourceSeries {
  readonly source: AppointmentSource;
  readonly values: readonly number[];
}

/** §4.1 bookings over time, stacked by the three chart sources (Voice, WhatsApp, Web Chat). */
export function bookingsBySource(
  appointments: readonly OverviewBookingPoint[],
  days: number,
  now = new Date(),
): readonly SourceSeries[] {
  return BOOKING_CHART_SOURCES.map((source) => {
    const values = new Array<number>(days).fill(0);
    for (const appt of appointments) {
      if (appt.source !== source) continue;
      const i = bucketIndex(appt.bookedAtUtc, days, now);
      if (i >= 0) values[i] += 1;
    }
    return { source, values };
  });
}

/** §4.5 calls over time — daily count of call interactions. */
export function callsPerDay(
  calls: readonly { readonly atUtc: string }[],
  days: number,
  now = new Date(),
): readonly number[] {
  const values = new Array<number>(days).fill(0);
  for (const call of calls) {
    const i = bucketIndex(call.atUtc, days, now);
    if (i >= 0) values[i] += 1;
  }
  return values;
}

/** §4.5 minutes over time — daily sum of call minutes (rounded per day). */
export function minutesPerDay(
  calls: readonly { readonly atUtc: string; readonly durationSeconds: number }[],
  days: number,
  now = new Date(),
): readonly number[] {
  const seconds = new Array<number>(days).fill(0);
  for (const call of calls) {
    const i = bucketIndex(call.atUtc, days, now);
    if (i >= 0) seconds[i] += call.durationSeconds;
  }
  return seconds.map((s) => Math.round(s / 60));
}

/** §4.5 average first-audio response (ms) over time — daily mean. */
export function firstAudioPerDay(
  calls: readonly { readonly atUtc: string; readonly firstAudioResponseMs: number }[],
  days: number,
  now = new Date(),
): readonly (number | null)[] {
  const sums = new Array<number>(days).fill(0);
  const counts = new Array<number>(days).fill(0);
  for (const call of calls) {
    const i = bucketIndex(call.atUtc, days, now);
    if (i >= 0) {
      sums[i] += call.firstAudioResponseMs;
      counts[i] += 1;
    }
  }
  return sums.map((s, i) => (counts[i] > 0 ? Math.round(s / counts[i]) : null));
}
