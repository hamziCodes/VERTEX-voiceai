// JS port of supabase/functions/_shared/appointment-time.ts (Deno TS -> Node ESM).
// Deterministic appointment-time parser: turns free-text appointment phrases
// ("tomorrow two PM", "Thursday the ninth at 9 AM") into a concrete UTC instant,
// rule-based only — no LLM, no network. When the text is ambiguous (no explicit
// time, no concrete date, or a weekday/date mismatch) it NEVER guesses:
// status is "ambiguous" and startsAt is null. All date math respects the given
// IANA timezone, including DST, via Intl.DateTimeFormat.
//
// Kept semantically identical to the TS original; keep the two in sync.

/**
 * @typedef {Object} ParsedApptTime
 * @property {string|null} startsAt ISO-8601 UTC, or null
 * @property {"parsed"|"ambiguous"|"unparseable"} status
 * @property {"low"|"medium"|"high"|null} confidence
 * @property {string} method which rule matched, for audit
 */

const WEEKDAY_NAMES = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
const WEEKDAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_NAMES = [
  "january", "february", "march", "april", "may", "june",
  "july", "august", "september", "october", "november", "december",
];

/** @type {Record<string, number>} */
const HOUR_WORDS = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6,
  seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12,
};

/** @type {Record<string, number>} */
const MINUTE_WORDS = {
  "fifteen": 15, "thirty": 30, "forty five": 45,
};

/** @type {Record<string, number>} */
const ORDINAL_WORDS = {
  first: 1, second: 2, third: 3, fourth: 4, fifth: 5, sixth: 6, seventh: 7,
  eighth: 8, ninth: 9, tenth: 10, eleventh: 11, twelfth: 12, thirteenth: 13,
  fourteenth: 14, fifteenth: 15, sixteenth: 16, seventeenth: 17, eighteenth: 18,
  nineteenth: 19, twentieth: 20, "twenty first": 21, "twenty second": 22,
  "twenty third": 23, "twenty fourth": 24, "twenty fifth": 25, "twenty sixth": 26,
  "twenty seventh": 27, "twenty eighth": 28, "twenty ninth": 29, thirtieth: 30,
  "thirty first": 31,
};

/** @param {string[]} words */
const alternation = (words) => words.slice().sort((a, b) => b.length - a.length).join("|");
const HOUR_WORD_ALT = alternation(Object.keys(HOUR_WORDS));
const MINUTE_WORD_ALT = alternation(Object.keys(MINUTE_WORDS));
const ORDINAL_ALT = alternation(Object.keys(ORDINAL_WORDS));
const MONTH_ALT = alternation(MONTH_NAMES);
const WEEKDAY_ALT = alternation(WEEKDAY_NAMES);

// Times only count as explicit when carrying a meridiem (or "noon").
const DIGIT_TIME_RE = new RegExp(String.raw`\b(\d{1,2})(?::(\d{2}))?\s*([ap])\s?m\b`);
const WORD_TIME_RE = new RegExp(String.raw`\b(${HOUR_WORD_ALT})(?:\s+(${MINUTE_WORD_ALT}))?\s+([ap])\s?m\b`);
const NOON_RE = /\bnoon\b|\bmidday\b/;
const MIDNIGHT_RE = /\bmidnight\b/;
const MONTH_DAY_RE = new RegExp(String.raw`\b(${MONTH_ALT})\s+(?:the\s+)?(?:(\d{1,2})(?:st|nd|rd|th)?|(${ORDINAL_ALT}))\b`);
const DAY_MONTH_RE = new RegExp(String.raw`\b(?:the\s+)?(?:(\d{1,2})(?:st|nd|rd|th)?|(${ORDINAL_ALT}))\s+(?:of\s+)?(${MONTH_ALT})\b`);
const DAY_ONLY_RE = new RegExp(String.raw`\bthe\s+(?:(\d{1,2})(?:st|nd|rd|th)?|(${ORDINAL_ALT}))\b`);
const WEEKDAY_RE = new RegExp(String.raw`\b(?:next\s+|this\s+(?:coming\s+)?)?(${WEEKDAY_ALT})\b`);
const DAYPART_RE = /\b(morning|afternoon|evening|tonight|night)\b/;
const NEXT_WEEK_RE = /\bnext\s+week\b/;
const TODAY_RE = /\btoday\b|\btonight\b/;
const TOMORROW_RE = /\btomorrow\b/;

/**
 * @param {string|null|undefined} text
 * @param {string} referenceUtc ISO instant the phrase is relative to (usually booked_at)
 * @param {string} timezone IANA zone, e.g. "America/Chicago"
 * @returns {ParsedApptTime}
 */
export function parseAppointmentText(text, referenceUtc, timezone) {
  const raw = (text ?? "").trim();
  if (!raw) return result(null, "unparseable", null, "empty");

  const reference = new Date(referenceUtc);
  if (isNaN(reference.getTime())) return result(null, "unparseable", null, "invalid_reference");

  const norm = normalize(raw);
  const refLocal = getLocalParts(reference, timezone);
  const refDate = { year: refLocal.year, month: refLocal.month, day: refLocal.day };

  const time = extractTime(norm);
  const hasMidnight = MIDNIGHT_RE.test(norm);
  const hasDaypart = DAYPART_RE.test(norm);
  const monthDay = extractMonthDay(norm);
  const dayOfMonth = monthDay ? null : extractDayOfMonth(norm);
  const weekday = extractWeekday(norm);
  const isToday = TODAY_RE.test(norm);
  const isTomorrow = TOMORROW_RE.test(norm);
  const isNextWeek = NEXT_WEEK_RE.test(norm);

  // Resolve the target calendar date (in the clinic timezone).
  let target = null;
  let dateMethod = "";
  if (monthDay) {
    target = resolveMonthDay(monthDay.month, monthDay.day, refDate);
    if (!target) return result(null, "ambiguous", "low", "invalid_date");
    dateMethod = "explicit_date";
  } else if (dayOfMonth !== null) {
    target = resolveDayOfMonth(dayOfMonth, refDate);
    if (!target) return result(null, "ambiguous", "low", "invalid_date");
    dateMethod = "day_of_month";
  } else if (isTomorrow) {
    target = addDays(refDate, 1);
    dateMethod = "tomorrow";
  } else if (isToday) {
    target = refDate;
    dateMethod = "today";
  } else if (weekday !== null) {
    // Bare weekday = the NEXT occurrence strictly after the reference date.
    const daysAhead = ((weekday - weekdayOf(refDate) + 7 - 1) % 7) + 1;
    target = addDays(refDate, daysAhead);
    dateMethod = "weekday";
  }

  // Weekday cross-check: when a weekday is named alongside an independently
  // resolved date, a disagreement is a possible transcription error — never pick a side.
  if (target !== null && weekday !== null && dateMethod !== "weekday" && weekdayOf(target) !== weekday) {
    return result(null, "ambiguous", "low", `${dateMethod}_weekday_mismatch`);
  }

  if (target === null) {
    if (isNextWeek) return result(null, "ambiguous", "low", "next_week");
    if (time) return result(null, "ambiguous", "low", "time_only_no_date");
    if (hasMidnight) return result(null, "ambiguous", "low", "midnight_no_date");
    if (hasDaypart) return result(null, "ambiguous", "low", "daypart_only");
    return result(null, "unparseable", null, "no_match");
  }

  // "midnight" is inherently ambiguous (start or end of the named day) — never guess.
  if (!time && hasMidnight) return result(null, "ambiguous", "low", `${dateMethod}_midnight`);

  // A daypart ("morning", "evening", ...) is not an explicit time — never invent an hour.
  if (!time) {
    const suffix = hasDaypart ? "_daypart_no_time" : "_no_time";
    return result(null, "ambiguous", "low", `${dateMethod}${suffix}`);
  }

  const startsAt = zonedTimeToUtc(target.year, target.month, target.day, time.hour, time.minute, timezone);
  const confidence = dateMethod === "weekday" ? "medium" : "high";
  return result(startsAt.toISOString(), "parsed", confidence, `${dateMethod}_time`);
}

/**
 * @param {string|null} startsAt
 * @param {"parsed"|"ambiguous"|"unparseable"} status
 * @param {"low"|"medium"|"high"|null} confidence
 * @param {string} method
 * @returns {ParsedApptTime}
 */
function result(startsAt, status, confidence, method) {
  return { startsAt, status, confidence, method };
}

/** @param {string} text */
function normalize(text) {
  return text
    .toLowerCase()
    .replace(/[.,!?;]/g, " ")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** @param {string} norm @returns {{hour:number,minute:number}|null} */
function extractTime(norm) {
  const digit = norm.match(DIGIT_TIME_RE);
  if (digit) {
    const hour = parseInt(digit[1], 10);
    const minute = digit[2] ? parseInt(digit[2], 10) : 0;
    if (hour >= 1 && hour <= 12 && minute >= 0 && minute <= 59) {
      return { hour: toHour24(hour, digit[3]), minute };
    }
    return null;
  }
  const word = norm.match(WORD_TIME_RE);
  if (word) {
    const hour = HOUR_WORDS[word[1]];
    const minute = word[2] ? MINUTE_WORDS[word[2]] : 0;
    return { hour: toHour24(hour, word[3]), minute };
  }
  if (NOON_RE.test(norm)) return { hour: 12, minute: 0 };
  return null;
}

/** @param {number} hour12 @param {string} meridiem */
function toHour24(hour12, meridiem) {
  if (meridiem === "a") return hour12 === 12 ? 0 : hour12;
  return hour12 === 12 ? 12 : hour12 + 12;
}

/** @param {string} norm @returns {{month:number,day:number}|null} */
function extractMonthDay(norm) {
  const md = norm.match(MONTH_DAY_RE);
  if (md) {
    const day = md[2] ? parseInt(md[2], 10) : ORDINAL_WORDS[md[3]];
    return { month: MONTH_NAMES.indexOf(md[1]) + 1, day };
  }
  const dm = norm.match(DAY_MONTH_RE);
  if (dm) {
    const day = dm[1] ? parseInt(dm[1], 10) : ORDINAL_WORDS[dm[2]];
    return { month: MONTH_NAMES.indexOf(dm[3]) + 1, day };
  }
  return null;
}

/** @param {string} norm @returns {number|null} */
function extractDayOfMonth(norm) {
  const m = norm.match(DAY_ONLY_RE);
  if (!m) return null;
  const day = m[1] ? parseInt(m[1], 10) : ORDINAL_WORDS[m[2]];
  return day >= 1 && day <= 31 ? day : null;
}

/** @param {string} norm @returns {number|null} */
function extractWeekday(norm) {
  const m = norm.match(WEEKDAY_RE);
  return m ? WEEKDAY_NAMES.indexOf(m[1]) : null;
}

// "July 15th" -> this year if the date is today or later, otherwise next year.
/** @param {number} month @param {number} day @param {{year:number,month:number,day:number}} ref */
function resolveMonthDay(month, day, ref) {
  for (const year of [ref.year, ref.year + 1]) {
    const candidate = { year, month, day };
    if (!isRealDate(candidate)) continue;
    if (compareDates(candidate, ref) >= 0) return candidate;
  }
  return null;
}

// "the 15th" -> this month if that day is today or later, otherwise next month.
/** @param {number} day @param {{year:number,month:number,day:number}} ref */
function resolveDayOfMonth(day, ref) {
  for (let offset = 0; offset <= 2; offset++) {
    const monthIndex = ref.month - 1 + offset;
    const candidate = {
      year: ref.year + Math.floor(monthIndex / 12),
      month: (monthIndex % 12) + 1,
      day,
    };
    if (!isRealDate(candidate)) continue;
    if (compareDates(candidate, ref) >= 0) return candidate;
  }
  return null;
}

/** @param {{year:number,month:number,day:number}} d */
function isRealDate(d) {
  const probe = new Date(Date.UTC(d.year, d.month - 1, d.day));
  return probe.getUTCFullYear() === d.year &&
    probe.getUTCMonth() === d.month - 1 &&
    probe.getUTCDate() === d.day;
}

/** @param {{year:number,month:number,day:number}} a @param {{year:number,month:number,day:number}} b */
function compareDates(a, b) {
  return Date.UTC(a.year, a.month - 1, a.day) - Date.UTC(b.year, b.month - 1, b.day);
}

/** @param {{year:number,month:number,day:number}} d @param {number} days */
export function addDays(d, days) {
  const shifted = new Date(Date.UTC(d.year, d.month - 1, d.day + days));
  return { year: shifted.getUTCFullYear(), month: shifted.getUTCMonth() + 1, day: shifted.getUTCDate() };
}

/** Weekday of a calendar date, 0 = Sunday. @param {{year:number,month:number,day:number}} d */
export function weekdayOf(d) {
  return new Date(Date.UTC(d.year, d.month - 1, d.day)).getUTCDay();
}

/**
 * Wall-clock parts of an instant in a zone.
 * @param {Date} instant
 * @param {string} timeZone
 * @returns {{year:number,month:number,day:number,hour:number,minute:number,second:number,weekday:number}} weekday 0 = Sunday
 */
export function getLocalParts(instant, timeZone) {
  const dtf = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    weekday: "short",
    hourCycle: "h23",
  });
  /** @type {Record<string, string>} */
  const map = {};
  for (const part of dtf.formatToParts(instant)) {
    if (part.type !== "literal") map[part.type] = part.value;
  }
  return {
    year: parseInt(map.year, 10),
    month: parseInt(map.month, 10),
    day: parseInt(map.day, 10),
    hour: parseInt(map.hour, 10),
    minute: parseInt(map.minute, 10),
    second: parseInt(map.second, 10),
    weekday: WEEKDAY_SHORT.indexOf(map.weekday),
  };
}

// Milliseconds the zone's wall clock is ahead of UTC at the given instant
// (negative for America/Chicago).
/** @param {Date} instant @param {string} timeZone */
function tzOffsetMs(instant, timeZone) {
  const p = getLocalParts(instant, timeZone);
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  const truncated = Math.floor(instant.getTime() / 1000) * 1000;
  return asUtc - truncated;
}

/**
 * Converts a wall-clock time in the given IANA zone to the UTC instant, handling DST.
 * Uses the standard two-pass offset refinement; for wall times that don't exist
 * (spring-forward gap) or repeat (fall-back) the result is deterministic.
 * @param {number} year @param {number} month 1-12 @param {number} day
 * @param {number} hour @param {number} minute @param {string} timeZone
 * @returns {Date}
 */
export function zonedTimeToUtc(year, month, day, hour, minute, timeZone) {
  const asUtc = Date.UTC(year, month - 1, day, hour, minute);
  let guess = asUtc;
  for (let i = 0; i < 2; i++) {
    guess = asUtc - tzOffsetMs(new Date(guess), timeZone);
  }
  return new Date(guess);
}
