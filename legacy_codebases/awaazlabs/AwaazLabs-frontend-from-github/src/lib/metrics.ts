/**
 * DERIVED METRICS — the single home for every number that appears on more than one tab.
 *
 * FROZEN FILE (Foundation).
 *
 * Guide Part H step 4 requires Phase 3 to verify these cross-tab wirings against the mock
 * data:
 *   - Overview quality pulse (§4.4)      == Quality tab's current score (§12.2)
 *   - Overview revenue estimate (§4.3)   == Organization's configured avg appointment value
 *   - Reengagement revenue (§14.1)       feeds the Overview revenue card (§4.3)
 *   - VOB status chips agree across Overview, VOB Agent, VOB Queue, Appointments
 *
 * Those equalities hold **by construction** here, because each is computed exactly once and
 * imported by both surfaces. If Overview and Quality each derived the aggregate grade
 * independently, they would drift the moment one rounded differently — and Phase 3 would
 * catch it as a defect. This file exists to make that class of bug impossible.
 */

import { mockNow } from '@/mock/orgs';
import type { Session } from '@/mock/data-access';
import type {
  Appointment,
  CallInteraction,
  MockOrganization,
  OrgFixture,
  VobRecord,
} from '@/mock/schema';
import {
  ESCALATION_ACK_THRESHOLD_MINUTES,
  OPTIMIZATION_APPLIED_STATUSES,
  OPTIMIZATION_FLAGGED_STATUSES,
  VOB_AGING_THRESHOLD_HOURS,
  isVobInProgress,
  isVobNeedsAttention,
  isVobOverviewNeedsAttention,
  isVobTerminal,
} from '@/shared/status-models';
import type { VobInProgressStatus } from '@/shared/status-models';
import { ratio } from './format';

/* ==================================================================================
 * Scoping — §2.4 the global location filter applies to every metric on every tab
 * ================================================================================== */

interface HasLocation {
  readonly locationId: string;
}

export function scopeToLocation<T extends HasLocation>(rows: readonly T[], session: Session): readonly T[] {
  if (session.locationId === null) return rows;
  return rows.filter((r) => r.locationId === session.locationId);
}

/* ==================================================================================
 * Elapsed time + time windows (windows still anchored to MOCK_NOW_UTC for fixtures)
 * ================================================================================== */

const MS_PER_HOUR = 3_600_000;
const MS_PER_DAY = 86_400_000;

/** Elapsed time from `iso` to now — always uses the real clock (not MOCK_NOW). */
export function hoursSince(iso: string): number {
  return (Date.now() - new Date(iso).getTime()) / MS_PER_HOUR;
}

/** Elapsed days from `iso` to now — always uses the real clock (not MOCK_NOW). */
export function daysSince(iso: string): number {
  return (Date.now() - new Date(iso).getTime()) / MS_PER_DAY;
}

function isSameUtcDay(iso: string, reference: Date): boolean {
  const d = new Date(iso);
  return (
    d.getUTCFullYear() === reference.getUTCFullYear() &&
    d.getUTCMonth() === reference.getUTCMonth() &&
    d.getUTCDate() === reference.getUTCDate()
  );
}

export function isToday(iso: string): boolean {
  return isSameUtcDay(iso, mockNow());
}

/** Trailing N days, inclusive of now, exclusive of the future. */
export function isWithinTrailingDays(iso: string, days: number): boolean {
  const age = daysSince(iso);
  return age >= 0 && age <= days;
}

export function isWithinNextDays(iso: string, days: number): boolean {
  const age = daysSince(iso);
  return age < 0 && -age <= days;
}

/** §4.1 "delta vs same weekday last week" — the same UTC weekday, 7 days back. */
export function isSameWeekdayLastWeek(iso: string): boolean {
  const target = new Date(mockNow().getTime() - 7 * MS_PER_DAY);
  return isSameUtcDay(iso, target);
}

/** "This week" = trailing 7 days. Used by §4.1, §4.2, §11.3. */
export function isThisWeek(iso: string): boolean {
  return isWithinTrailingDays(iso, 7);
}

export function isThisMonth(iso: string): boolean {
  const d = new Date(iso);
  const now = mockNow();
  return d.getUTCFullYear() === now.getUTCFullYear() && d.getUTCMonth() === now.getUTCMonth();
}

/* ==================================================================================
 * §12.2 — Aggregate quality score.
 *
 * THE canonical definition. Overview's §4.4 quality pulse and the Quality tab's §12.2
 * "current quality score" both read this function, so they cannot disagree.
 * ================================================================================== */

export function aggregateQualityScore(calls: readonly CallInteraction[]): number | null {
  const graded = calls.filter((c) => c.grade !== null);
  if (graded.length === 0) return null;
  const sum = graded.reduce((acc, c) => acc + (c.grade?.overall ?? 0), 0);
  return Math.round(sum / graded.length);
}

/** §4.4 "30-day trend sparkline" · §12.2 "30-day and 90-day trend line". One implementation. */
export function qualityTrend(calls: readonly CallInteraction[], days: number): readonly number[] {
  const buckets: number[][] = Array.from({ length: days }, () => []);

  for (const call of calls) {
    if (call.grade === null) continue;
    const age = Math.floor(daysSince(call.atUtc));
    if (age < 0 || age >= days) continue;
    buckets[days - 1 - age].push(call.grade.overall);
  }

  // Carry the last known value across days with no graded calls, rather than plotting a
  // zero — a day with no calls is not a day of terrible quality.
  const out: number[] = [];
  let last = 0;
  for (const bucket of buckets) {
    if (bucket.length > 0) {
      last = bucket.reduce((a, b) => a + b, 0) / bucket.length;
    }
    out.push(Math.round(last * 10) / 10);
  }
  return out;
}

/**
 * §12.1 loop stage counts. See BUILD_NOTES.md § B10 for why "Optimizations applied" maps to
 * `deployed | verified` and "Flagged for optimization" to `detected | in_tuning`.
 */
export interface LoopCounts {
  readonly callsCompleted: number;
  readonly analyzedAndGraded: number;
  readonly flaggedForOptimization: number;
  readonly optimizationsApplied: number;
}

export function loopCounts(fixture: OrgFixture, session: Session): LoopCounts {
  const calls = scopeToLocation(fixture.calls, session);
  const completed = calls.filter((c) => c.disposition !== 'abandoned' && c.disposition !== 'no_answer');

  return {
    callsCompleted: completed.length,
    analyzedAndGraded: calls.filter((c) => c.grade !== null).length,
    flaggedForOptimization: fixture.optimizationEvents.filter((e) =>
      (OPTIMIZATION_FLAGGED_STATUSES as readonly string[]).includes(e.status),
    ).length,
    optimizationsApplied: fixture.optimizationEvents.filter((e) =>
      (OPTIMIZATION_APPLIED_STATUSES as readonly string[]).includes(e.status),
    ).length,
  };
}

/** §4.4 "count of optimization events this month". */
export function optimizationEventsThisMonth(fixture: OrgFixture): number {
  return fixture.optimizationEvents.filter((e) => isThisMonth(e.detectedAtUtc)).length;
}

/* ==================================================================================
 * §4.2 / §7 / §8 — VOB. One status taxonomy, four surfaces.
 * ================================================================================== */

export interface VobCounts {
  readonly inProgress: number;
  readonly inProgressBySubStatus: Readonly<Record<VobInProgressStatus | 'queued', number>>;
  readonly completedToday: number;
  readonly completedThisWeek: number;
  /** verified / all terminal, this week. Null when nothing terminal happened. */
  readonly verifiedRateThisWeek: number | null;
  /** §4.2's narrower trio: unable_to_verify + member_not_found + inactive_policy. */
  readonly overviewNeedsAttention: number;
  /** §7.3's worklist definition: every terminal status except `verified`. */
  readonly worklistNeedsAttention: number;
}

export function vobCounts(fixture: OrgFixture, session: Session): VobCounts {
  const rows = scopeToLocation(fixture.vobRecords, session);

  const terminalThisWeek = rows.filter(
    (v) => isVobTerminal(v.status) && v.lastAttemptAtUtc !== null && isThisWeek(v.lastAttemptAtUtc),
  );
  const verifiedThisWeek = terminalThisWeek.filter((v) => v.status === 'verified');

  return {
    inProgress: rows.filter((v) => v.status === 'queued' || isVobInProgress(v.status)).length,
    inProgressBySubStatus: {
      queued: rows.filter((v) => v.status === 'queued').length,
      dialing: rows.filter((v) => v.status === 'dialing').length,
      on_call: rows.filter((v) => v.status === 'on_call').length,
      pending_callback: rows.filter((v) => v.status === 'pending_callback').length,
    },
    completedToday: rows.filter(
      (v) => isVobTerminal(v.status) && v.lastAttemptAtUtc !== null && isToday(v.lastAttemptAtUtc),
    ).length,
    completedThisWeek: terminalThisWeek.length,
    verifiedRateThisWeek: ratio(verifiedThisWeek.length, terminalThisWeek.length),
    overviewNeedsAttention: rows.filter((v) => isVobOverviewNeedsAttention(v.status)).length,
    worklistNeedsAttention: rows.filter((v) => isVobNeedsAttention(v.status)).length,
  };
}

/** §8.1 "amber past 24 hours in a non-terminal state, red past 48 hours". */
export type AgingLevel = 'none' | 'amber' | 'red';

export function agingLevel(record: VobRecord): AgingLevel {
  if (isVobTerminal(record.status)) return 'none';
  const age = hoursSince(record.requestedAtUtc);
  if (age >= VOB_AGING_THRESHOLD_HOURS.red) return 'red';
  if (age >= VOB_AGING_THRESHOLD_HOURS.amber) return 'amber';
  return 'none';
}

/* ==================================================================================
 * §4.1 / §5.1 — Appointments
 * ================================================================================== */

export interface AppointmentStats {
  readonly bookedToday: number;
  readonly bookedSameWeekdayLastWeek: number;
  readonly bookedThisWeek: number;
  /** §4.1 "booking rate: booked divided by completed inbound interactions". */
  readonly bookingRateThisWeek: number | null;
  readonly upcomingNext7Days: number;
  readonly noShowsAndCancellationsThisWeek: number;
  readonly noShowCancelRateThisWeek: number | null;
  /** §5.1 "confirmation rate (confirmed / booked with a scheduled confirmation attempt)". */
  readonly confirmationRate: number | null;
  /** §5.1 "no-show rate trailing 30 days". */
  readonly noShowRate30d: number | null;
}

export function appointmentStats(fixture: OrgFixture, session: Session): AppointmentStats {
  const appts = scopeToLocation(fixture.appointments, session);
  const calls = scopeToLocation(fixture.calls, session);

  const chats = scopeToLocation(fixture.chats, session);
  const bookedThisWeek = appts.filter((a) => isThisWeek(a.bookedAtUtc));

  /**
   * §4.1's denominator is "completed inbound **interactions**" — not "calls".
   *
   * Chat sessions are inbound interactions: §1.4 describes the chat agents as "performing
   * the receptionist function on text channels", and §4.1's own chart stacks bookings by
   * Voice / WhatsApp / Web Chat. Counting only calls would divide bookings from three
   * channels by the interactions of one, producing a booking rate above 100%.
   */
  const completedInboundCalls = calls.filter(
    (c) =>
      c.direction === 'inbound' &&
      isThisWeek(c.atUtc) &&
      c.disposition !== 'abandoned' &&
      c.disposition !== 'no_answer',
  );
  const completedChatSessions = chats.filter((c) => isThisWeek(c.atUtc) && c.outcome !== 'escalated');
  const completedInboundThisWeek = [...completedInboundCalls, ...completedChatSessions];

  const thisWeekAll = appts.filter((a) => isThisWeek(a.startsAtUtc));
  const noShowCancel = thisWeekAll.filter((a) => a.status === 'no_show' || a.status === 'cancelled');

  // §5.1: the denominator is bookings that actually had a confirmation attempt scheduled —
  // not all bookings. Counting all bookings would understate the rate for clinics that
  // never attempt confirmation.
  const withConfirmationAttempt = appts.filter((a) => a.confirmationAttempts.length > 0);
  const confirmed = withConfirmationAttempt.filter(
    (a) => a.status === 'confirmed' || a.status === 'completed' || a.status === 'rescheduled',
  );

  const trailing30 = appts.filter((a) => isWithinTrailingDays(a.startsAtUtc, 30));
  const trailing30Resolved = trailing30.filter(
    (a) => a.status === 'completed' || a.status === 'no_show',
  );

  return {
    bookedToday: appts.filter((a) => isToday(a.bookedAtUtc)).length,
    bookedSameWeekdayLastWeek: appts.filter((a) => isSameWeekdayLastWeek(a.bookedAtUtc)).length,
    bookedThisWeek: bookedThisWeek.length,
    bookingRateThisWeek: ratio(bookedThisWeek.length, completedInboundThisWeek.length),
    upcomingNext7Days: appts.filter(
      (a) => isWithinNextDays(a.startsAtUtc, 7) && a.status !== 'cancelled' && a.status !== 'no_show',
    ).length,
    noShowsAndCancellationsThisWeek: noShowCancel.length,
    noShowCancelRateThisWeek: ratio(noShowCancel.length, thisWeekAll.length),
    confirmationRate: ratio(confirmed.length, withConfirmationAttempt.length),
    noShowRate30d: ratio(
      trailing30Resolved.filter((a) => a.status === 'no_show').length,
      trailing30Resolved.length,
    ),
  };
}

/* ==================================================================================
 * §4.3 — Revenue recovered (estimate)
 *
 * "(after-hours bookings + reengagement bookings + recovered no-shows) multiplied by the
 *  clinic-configured average appointment value."
 *
 * §14.1's reengagement revenue estimate reads `reengagementBookings` from this same
 * function, which is what makes the two tabs agree — a Phase 3 requirement.
 * ================================================================================== */

export interface RevenueEstimate {
  readonly afterHoursBookings: number;
  readonly reengagementBookings: number;
  readonly recoveredNoShows: number;
  readonly avgAppointmentValueUsd: number;
  readonly totalUsd: number;
}

/**
 * "Recovered no-show": an appointment that reached `no_show`, for which a later appointment
 * exists for the same contact within the period. The spec never defines the term — see
 * BUILD_NOTES.md § B5. The §4.3 tooltip states this definition verbatim so the reader is
 * never misled about what the estimate counts.
 */
function countRecoveredNoShows(appointments: readonly Appointment[]): number {
  const noShows = appointments.filter((a) => a.status === 'no_show' && isThisMonth(a.startsAtUtc));

  let recovered = 0;
  for (const missed of noShows) {
    const rebooked = appointments.some(
      (a) =>
        a.contactId === missed.contactId &&
        a.id !== missed.id &&
        new Date(a.bookedAtUtc).getTime() > new Date(missed.startsAtUtc).getTime(),
    );
    if (rebooked) recovered += 1;
  }
  return recovered;
}

/**
 * Returns `null` when the org has not configured an average appointment value.
 * §4.3: "card hides if average value is unset." Returning 0 would render a misleading $0.
 */
export function revenueRecoveredEstimate(
  fixture: OrgFixture,
  org: MockOrganization,
  session: Session,
): RevenueEstimate | null {
  if (org.avgAppointmentValueUsd === null) return null;

  const appts = scopeToLocation(fixture.appointments, session);
  const thisMonth = appts.filter((a) => isThisMonth(a.bookedAtUtc));

  const afterHoursBookings = thisMonth.filter((a) => a.afterHours).length;
  const reengagementBookings = thisMonth.filter((a) => a.bookedByAgent === 'reengagement').length;
  const recoveredNoShows = countRecoveredNoShows(appts);

  const units = afterHoursBookings + reengagementBookings + recoveredNoShows;

  return {
    afterHoursBookings,
    reengagementBookings,
    recoveredNoShows,
    avgAppointmentValueUsd: org.avgAppointmentValueUsd,
    totalUsd: units * org.avgAppointmentValueUsd,
  };
}

/* ==================================================================================
 * §4.5 — Operational telemetry
 * ================================================================================== */

export interface Telemetry {
  readonly callsToday: number;
  readonly minutesToday: number;
  readonly avgDurationSeconds: number | null;
  readonly avgCostPerInteractionUsd: number | null;
  readonly avgFirstAudioResponseMs: number | null;
  readonly successRate: number | null;
  readonly completedCount: number;
  readonly attemptedCount: number;
  readonly liveCallsNow: number;
}

/** §4.5 "target line at 800 ms". Also §9.1's latency target. */
export const FIRST_AUDIO_TARGET_MS = 800;

export function telemetry(fixture: OrgFixture, session: Session): Telemetry {
  const calls = scopeToLocation(fixture.calls, session);
  const today = calls.filter((c) => isToday(c.atUtc));
  const chats = scopeToLocation(fixture.chats, session);

  const completed = calls.filter((c) => c.disposition !== 'abandoned' && c.disposition !== 'no_answer');
  const totalInteractions = calls.length + chats.length;
  const totalCost = calls.reduce((acc, c) => acc + c.costUsd, 0);

  return {
    callsToday: today.length,
    minutesToday: Math.round(today.reduce((acc, c) => acc + c.durationSeconds, 0) / 60),
    avgDurationSeconds: calls.length ? calls.reduce((a, c) => a + c.durationSeconds, 0) / calls.length : null,
    avgCostPerInteractionUsd: totalInteractions ? totalCost / totalInteractions : null,
    avgFirstAudioResponseMs: calls.length
      ? calls.reduce((a, c) => a + c.firstAudioResponseMs, 0) / calls.length
      : null,
    successRate: ratio(completed.length, calls.length),
    completedCount: completed.length,
    attemptedCount: calls.length,
    liveCallsNow: fixture.liveCallsNow,
  };
}

/* ==================================================================================
 * §4.6 — Attention banner
 *
 * "A dismissible red banner renders above Section A when any of the following are true:
 *  unacknowledged escalation older than the configured threshold, VOB needs-attention
 *  items older than 48 hours, any line health check failing, or usage at 90 percent or
 *  more of plan minutes. Each condition deep-links to its owning surface."
 *
 * Exactly four conditions. Not three, not five.
 * ================================================================================== */

export interface AttentionCondition {
  readonly key: 'escalation_aging' | 'vob_aging' | 'line_health' | 'usage_threshold';
  readonly message: string;
  readonly href: string;
}

export const USAGE_BANNER_THRESHOLD = 0.9;

export function attentionConditions(
  fixture: OrgFixture,
  org: MockOrganization,
  session: Session,
): readonly AttentionCondition[] {
  const conditions: AttentionCondition[] = [];

  // 1. Unacknowledged escalation older than its threshold (§11.2: 30 min Urgent, 4 hr else).
  const escalations = scopeToLocation(fixture.escalations, session);
  const agingEscalations = escalations.filter((e) => {
    if (e.status !== 'open') return false;
    const limit =
      e.trigger === 'triage_urgent_emergency'
        ? ESCALATION_ACK_THRESHOLD_MINUTES.urgent
        : ESCALATION_ACK_THRESHOLD_MINUTES.default;
    return hoursSince(e.atUtc) * 60 > limit;
  });
  if (agingEscalations.length > 0) {
    conditions.push({
      key: 'escalation_aging',
      message: `${agingEscalations.length} unacknowledged escalation${agingEscalations.length === 1 ? '' : 's'} past the acknowledgement threshold`,
      href: '/escalations',
    });
  }

  // 2. VOB needs-attention items older than 48 hours.
  const agingVob = scopeToLocation(fixture.vobRecords, session).filter((v) => agingLevel(v) === 'red');
  if (agingVob.length > 0) {
    conditions.push({
      key: 'vob_aging',
      message: `${agingVob.length} verification${agingVob.length === 1 ? '' : 's'} needing attention for over 48 hours`,
      href: '/vob-queue',
    });
  }

  // 3. Any line health check failing.
  const unhealthy = scopeToLocation(fixture.lines, session).filter((l) => !l.healthy);
  if (unhealthy.length > 0) {
    conditions.push({
      key: 'line_health',
      message: `${unhealthy.length} phone line${unhealthy.length === 1 ? '' : 's'} failing its health check`,
      href: '/settings/lines',
    });
  }

  // 4. Usage at 90% or more of plan minutes. Org-wide: a plan is not per-location.
  const usage = org.planMinutes > 0 ? fixture.minutesConsumed / org.planMinutes : 0;
  if (usage >= USAGE_BANNER_THRESHOLD) {
    conditions.push({
      key: 'usage_threshold',
      message: `Usage at ${Math.round(usage * 100)}% of plan minutes this cycle`,
      href: '/settings/billing',
    });
  }

  return conditions;
}
