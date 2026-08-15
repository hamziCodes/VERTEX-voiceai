// deno test _shared/appointment-time_test.ts
//
// Reference used for most tests: 2026-07-08T15:00:00Z = Wednesday, July 8 2026,
// 10:00 AM in America/Chicago (CDT, UTC-5). This makes the real production
// examples internally consistent: July 9 is a Thursday, July 12 a Sunday,
// July 15 a Wednesday.

import { parseAppointmentText } from "./appointment-time.ts";
import type { ParsedApptTime } from "./appointment-time.ts";

const TZ = "America/Chicago";
const REF = "2026-07-08T15:00:00Z";

function assertEquals<T>(actual: T, expected: T, context: string): void {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) throw new Error(`${context}: expected ${e}, got ${a}`);
}

function check(
  text: string | null | undefined,
  expected: Partial<ParsedApptTime>,
  ref: string = REF,
): void {
  const actual = parseAppointmentText(text, ref, TZ);
  for (const key of Object.keys(expected) as (keyof ParsedApptTime)[]) {
    assertEquals(
      actual[key],
      expected[key],
      `${JSON.stringify(text)} -> ${key} (full result: ${JSON.stringify(actual)})`,
    );
  }
}

Deno.test("today/tomorrow with explicit time -> parsed high", () => {
  check("tomorrow two PM", { startsAt: "2026-07-09T19:00:00.000Z", status: "parsed", confidence: "high", method: "tomorrow_time" });
  check("tomorrow at 2 PM", { startsAt: "2026-07-09T19:00:00.000Z", status: "parsed", confidence: "high" });
  check("Today, four pm.", { startsAt: "2026-07-08T21:00:00.000Z", status: "parsed", confidence: "high", method: "today_time" });
  check("Tomorrow, four PM", { startsAt: "2026-07-09T21:00:00.000Z", status: "parsed", confidence: "high" });
  check("tomorrow at 2:30 PM", { startsAt: "2026-07-09T19:30:00.000Z", status: "parsed", confidence: "high" });
});

Deno.test("tomorrow + weekday cross-check", () => {
  // Reference is Wednesday, so "tomorrow" IS Thursday -> consistent -> parsed high.
  check("tomorrow, Thursday at 4 PM", { startsAt: "2026-07-09T21:00:00.000Z", status: "parsed", confidence: "high" });
  // Tomorrow is Thursday, not Friday -> possible transcription error -> ambiguous.
  check("tomorrow, Friday at 4 PM", { startsAt: null, status: "ambiguous", method: "tomorrow_weekday_mismatch" });
});

Deno.test("bare weekday: next occurrence, parsed only with explicit time", () => {
  check("Tuesday", { startsAt: null, status: "ambiguous", method: "weekday_no_time" });
  // Next Tuesday after Wednesday July 8 is July 14.
  check("Tuesday at 3 PM", { startsAt: "2026-07-14T20:00:00.000Z", status: "parsed", confidence: "medium", method: "weekday_time" });
  check("Tuesday at three PM", { startsAt: "2026-07-14T20:00:00.000Z", status: "parsed", confidence: "medium" });
  check("next Tuesday at 3 PM", { startsAt: "2026-07-14T20:00:00.000Z", status: "parsed", confidence: "medium" });
  // Reference IS a Wednesday -> "Wednesday" means NEXT Wednesday (July 15), never today.
  check("Wednesday at 2 PM", { startsAt: "2026-07-15T19:00:00.000Z", status: "parsed", confidence: "medium" });
});

Deno.test("dayparts without an explicit time are ambiguous (no invented hour)", () => {
  check("next Tuesday afternoon", { startsAt: null, status: "ambiguous", method: "weekday_daypart_no_time" });
  check("Sunday evening", { startsAt: null, status: "ambiguous", method: "weekday_daypart_no_time" });
  check("next Monday morning", { startsAt: null, status: "ambiguous", method: "weekday_daypart_no_time" });
  check("tonight", { startsAt: null, status: "ambiguous", method: "today_daypart_no_time" });
  check("later today", { startsAt: null, status: "ambiguous", method: "today_no_time" });
  check("morning", { startsAt: null, status: "ambiguous", method: "daypart_only" });
});

Deno.test("'next week' is ambiguous", () => {
  check("next week", { startsAt: null, status: "ambiguous", method: "next_week" });
});

Deno.test("time without a date is ambiguous", () => {
  check("10 AM", { startsAt: null, status: "ambiguous", method: "time_only_no_date" });
  check("noon", { startsAt: null, status: "ambiguous", method: "time_only_no_date" });
});

Deno.test("explicit dates: weekday cross-check and time requirement", () => {
  // July 15 2026 is a Wednesday -> consistent, but no time -> ambiguous.
  check("next Wednesday, July 15th", { startsAt: null, status: "ambiguous", method: "explicit_date_no_time" });
  check("Sunday, July 12th", { startsAt: null, status: "ambiguous", method: "explicit_date_no_time" });
  // July 15 2026 is a Wednesday, not a Tuesday -> mismatch -> ambiguous.
  check("Tuesday, July 15th", { startsAt: null, status: "ambiguous", method: "explicit_date_weekday_mismatch" });
  // Date + explicit time -> parsed high.
  check("July 15th at 3 PM", { startsAt: "2026-07-15T20:00:00.000Z", status: "parsed", confidence: "high", method: "explicit_date_time" });
  // Same-day explicit date is allowed.
  check("July 8th at 5 PM", { startsAt: "2026-07-08T22:00:00.000Z", status: "parsed", confidence: "high" });
});

Deno.test("day-of-month without month ('the 15th' / 'the ninth')", () => {
  // "Wednesday the 15th": July 15 is next, and it IS a Wednesday -> consistent, no time -> ambiguous.
  check("Wednesday the 15th", { startsAt: null, status: "ambiguous", method: "day_of_month_no_time" });
  // "Thursday the ninth at 9 AM": July 9 is a Thursday -> parsed high.
  check("Thursday the ninth at 9 AM", { startsAt: "2026-07-09T14:00:00.000Z", status: "parsed", confidence: "high", method: "day_of_month_time" });
  // "Friday the ninth": July 9 2026 is a Thursday -> mismatch.
  check("Friday the ninth at 9 AM", { startsAt: null, status: "ambiguous", method: "day_of_month_weekday_mismatch" });
});

Deno.test("noon / 12 PM / 12 AM / midnight", () => {
  check("tomorrow at noon", { startsAt: "2026-07-09T17:00:00.000Z", status: "parsed", confidence: "high" });
  check("tomorrow at 12 PM", { startsAt: "2026-07-09T17:00:00.000Z", status: "parsed", confidence: "high" });
  check("tomorrow at 12 AM", { startsAt: "2026-07-09T05:00:00.000Z", status: "parsed", confidence: "high" });
  // "midnight" is inherently ambiguous (start or end of the day) -> never guess.
  check("tomorrow at midnight", { startsAt: null, status: "ambiguous", method: "tomorrow_midnight" });
  check("midnight", { startsAt: null, status: "ambiguous", method: "midnight_no_date" });
});

Deno.test("missing or unusable text", () => {
  check("", { startsAt: null, status: "unparseable", confidence: null, method: "empty" });
  check("   ", { startsAt: null, status: "unparseable", confidence: null, method: "empty" });
  check(null, { startsAt: null, status: "unparseable", confidence: null, method: "empty" });
  check(undefined, { startsAt: null, status: "unparseable", confidence: null, method: "empty" });
  check("whenever works for you", { startsAt: null, status: "unparseable", confidence: null, method: "no_match" });
});

Deno.test("DST spring forward (America/Chicago, March 8 2026)", () => {
  // Reference: Saturday March 7 2026, 12:00 CST (UTC-6).
  const ref = "2026-03-07T18:00:00Z";
  // Same day, still CST: 2 PM = 20:00Z.
  check("today at 2 PM", { startsAt: "2026-03-07T20:00:00.000Z", status: "parsed", confidence: "high" }, ref);
  // Next day is past the spring-forward: 2 PM CDT = 19:00Z.
  check("tomorrow at 2 PM", { startsAt: "2026-03-08T19:00:00.000Z", status: "parsed", confidence: "high" }, ref);
  // 2:30 AM does not exist on March 8 -> algorithm still returns a deterministic instant.
  const gap = parseAppointmentText("tomorrow at 2:30 AM", ref, TZ);
  assertEquals(gap.status, "parsed", "spring-forward gap status");
  assertEquals(typeof gap.startsAt, "string", "spring-forward gap startsAt is set");
});

Deno.test("DST fall back (America/Chicago, November 1 2026)", () => {
  // Reference: Saturday October 31 2026, 10:00 CDT (UTC-5).
  const ref = "2026-10-31T15:00:00Z";
  // Next day is past the fall-back: 2 PM CST = 20:00Z.
  check("tomorrow at 2 PM", { startsAt: "2026-11-01T20:00:00.000Z", status: "parsed", confidence: "high" }, ref);
  // 1:30 AM occurs twice on November 1; the algorithm deterministically picks the
  // first occurrence (1:30 CDT = 06:30Z).
  check("tomorrow at 1:30 AM", { startsAt: "2026-11-01T06:30:00.000Z", status: "parsed" }, ref);
});

Deno.test("year rollover for explicit dates", () => {
  // Reference: Monday December 28 2026, 09:00 CST.
  const ref = "2026-12-28T15:00:00Z";
  check("January 5th at 10 AM", { startsAt: "2027-01-05T16:00:00.000Z", status: "parsed", confidence: "high" }, ref);
});

Deno.test("invalid reference timestamp", () => {
  const r = parseAppointmentText("tomorrow at 2 PM", "not-a-date", TZ);
  assertEquals(r.status, "unparseable", "invalid reference status");
  assertEquals(r.method, "invalid_reference", "invalid reference method");
});
