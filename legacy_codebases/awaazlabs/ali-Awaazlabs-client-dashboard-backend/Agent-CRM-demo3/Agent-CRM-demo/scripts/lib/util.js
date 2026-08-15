// Shared helpers for the data scripts. The normalization helpers (str, toE164,
// toBool, parseDateOnly, validateDob, cleanMemberId) are ports of
// supabase/functions/_shared/validate.ts so backfilled rows carry exactly the
// same semantics as rows written by the live pipeline.

import { createClient } from "@supabase/supabase-js";
import WebSocket from "ws";
import { getLocalParts } from "./appointment-time.js";

// Live functions read DEFAULT_COUNTRY_CODE from the env; for the backfill the
// agreed fallback is 92 (matches the deployed configuration).
export const DEFAULT_COUNTRY_CODE = "92";

export const TIMEZONE = "America/Chicago";

// Mirrors patients_phone_e164 CHECK in 20260709000100_appointments_domain.sql
export const E164_RE = /^\+[1-9][0-9]{6,14}$/;
// Mirrors patients_email_shape CHECK
export const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const NULL_STRINGS = new Set([
  "null", "undefined", "none", "n/a", "na",
  "not provided", "not listed", "unknown", "",
]);

/**
 * Null-normalization identical to _shared/validate.ts str().
 * @param {unknown} v
 * @returns {string|null}
 */
export function str(v) {
  if (v === null || v === undefined) return null;
  const s = String(v).trim();
  if (!s.length || NULL_STRINGS.has(s.toLowerCase())) return null;
  return s;
}

/** @param {string|null|undefined} input @returns {string} */
export function toDigits(input) {
  return (input ?? "").replace(/[^\d]/g, "");
}

/**
 * Port of _shared/validate.ts toE164 (with the 92 fallback baked in).
 * @param {string|null|undefined} input
 * @param {string} [defaultCc]
 * @returns {string} "" when no digits
 */
export function toE164(input, defaultCc = DEFAULT_COUNTRY_CODE) {
  let d = toDigits(input);
  if (!d) return "";
  if (d.startsWith("00")) d = d.slice(2);
  if (d.length === 11 && d.startsWith("0")) d = defaultCc + d.slice(1);
  if (d.length === 10) d = defaultCc + d;
  return "+" + d;
}

/** @param {unknown} v @returns {boolean|null} */
export function toBool(v) {
  if (v === true || v === false) return v;
  if (typeof v === "string") {
    const s = v.trim().toLowerCase();
    if (["yes", "true", "y", "1"].includes(s)) return true;
    if (["no", "false", "n", "0"].includes(s)) return false;
  }
  return null;
}

/** @param {string|null|undefined} input @returns {string|null} */
export function parseDateOnly(input) {
  if (!input) return null;
  const s = input.trim();
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) return isRealDate(+iso[1], +iso[2], +iso[3]) ? `${iso[1]}-${iso[2]}-${iso[3]}` : null;
  const slash = s.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})$/);
  if (slash) {
    const [, a, b, y] = slash;
    let yr = +y; if (yr < 100) yr += yr < 30 ? 2000 : 1900;
    const mo = +a, da = +b;
    return isRealDate(yr, mo, da) ? fmtDate(yr, mo, da) : null;
  }
  const months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"];
  const m = s.toLowerCase().match(/([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})/) ||
    s.toLowerCase().match(/(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+),?\s+(\d{4})/);
  if (m) {
    let mo, da, yr;
    if (isNaN(+m[1])) { mo = months.indexOf(m[1]) + 1; da = +m[2]; yr = +m[3]; }
    else { da = +m[1]; mo = months.indexOf(m[2]) + 1; yr = +m[3]; }
    if (mo > 0) return isRealDate(yr, mo, da) ? fmtDate(yr, mo, da) : null;
  }
  return null;
}

/** @param {number} y @param {number} m @param {number} d */
function isRealDate(y, m, d) {
  if (m < 1 || m > 12 || d < 1 || d > 31) return false;
  const dt = new Date(Date.UTC(y, m - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d;
}

/** @param {number} y @param {number} m @param {number} d */
export function fmtDate(y, m, d) {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/**
 * Port of _shared/validate.ts validateDob.
 * @param {string|null|undefined} input
 * @returns {{value: string|null, ok: boolean}}
 */
export function validateDob(input) {
  const v = parseDateOnly(input);
  if (!v) return { value: null, ok: input ? false : true };
  const ok = new Date(v + "T00:00:00Z").getTime() < Date.now();
  return { value: ok ? v : null, ok };
}

/** @param {string|null|undefined} input @returns {string|null} */
export function cleanMemberId(input) {
  if (!input) return null;
  const v = input.replace(/\s+/g, "").toUpperCase();
  return v.length ? v : null;
}

/**
 * Mirrors patients_name_not_garbage CHECK: length 2..100, no '@',
 * no run of 3+ consecutive digits.
 * @param {string} name
 * @returns {string|null} reason when garbage, null when acceptable
 */
export function nameGarbageReason(name) {
  if (name.length < 2 || name.length > 100) return "length_out_of_range";
  if (/@/.test(name)) return "contains_at_sign";
  if (/[0-9]{3}/.test(name)) return "contains_3plus_digits";
  return null;
}

/**
 * Normalize a free-form language value to the en/es/other enum.
 * @param {string|null|undefined} value
 * @returns {"en"|"es"|"other"}
 */
export function normalizeLanguage(value) {
  const v = (str(value) ?? "en").toLowerCase();
  if (v.startsWith("en")) return "en";
  if (v.startsWith("es") || v.startsWith("spa")) return "es";
  return "other";
}

const PATIENT_INSURANCE_STATUSES = new Set(["covered", "partial", "pending", "pending_form", "unknown", "self_pay"]);

/**
 * Map a bookings.insurance_status to the patients_insurance_status_enum.
 * @param {string|null|undefined} value
 * @returns {string}
 */
export function normalizeInsuranceStatus(value) {
  const v = str(value);
  if (v && PATIENT_INSURANCE_STATUSES.has(v)) return v;
  return "pending";
}

/**
 * true when the instant is inside Mon-Fri 08:00-17:00 in the given zone.
 * @param {Date} instant
 * @param {string} timezone
 */
export function isBusinessHours(instant, timezone = TIMEZONE) {
  const p = getLocalParts(instant, timezone);
  if (p.weekday === 0 || p.weekday === 6) return false;
  const minutes = p.hour * 60 + p.minute;
  return minutes >= 8 * 60 && minutes < 17 * 60;
}

/**
 * Service-role Supabase client from env. Aborts with a clear message when missing.
 */
export function adminClient() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) {
    console.error("FATAL: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars are required.");
    process.exit(1);
  }
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
    // supabase-js constructs a RealtimeClient eagerly and Node < 22 has no global
    // WebSocket. These scripts never open a channel; `ws` satisfies the constructor.
    realtime: { transport: WebSocket },
  });
}

/**
 * Fetch every row of a table, paginated. Throws on any error (nothing silent).
 * @param {import("@supabase/supabase-js").SupabaseClient} db
 * @param {string} table
 * @param {string} [select]
 * @param {string} [orderCol]
 * @returns {Promise<any[]>}
 */
export async function fetchAll(db, table, select = "*", orderCol = "created_at") {
  const pageSize = 1000;
  /** @type {any[]} */
  const rows = [];
  for (let from = 0; ; from += pageSize) {
    const { data, error } = await db.from(table)
      .select(select)
      .order(orderCol, { ascending: true })
      .order("id", { ascending: true })
      .range(from, from + pageSize - 1);
    if (error) throw new Error(`fetchAll(${table}) failed at offset ${from}: ${error.message}`);
    rows.push(...(data ?? []));
    if (!data || data.length < pageSize) break;
  }
  return rows;
}

/**
 * Exact row count of a table.
 * @param {import("@supabase/supabase-js").SupabaseClient} db
 * @param {string} table
 * @returns {Promise<number>}
 */
export async function countRows(db, table) {
  const { count, error } = await db.from(table).select("id", { count: "exact", head: true });
  if (error) throw new Error(`countRows(${table}) failed: ${error.message}`);
  return count ?? 0;
}

/**
 * Minimal CLI arg parser: --key value pairs.
 * @param {string[]} argv
 * @returns {Record<string, string>}
 */
export function parseArgs(argv) {
  /** @type {Record<string, string>} */
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) {
      args[argv[i].slice(2)] = argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[++i] : "true";
    }
  }
  return args;
}

/**
 * Print a two-column reconciliation table.
 * @param {string} title
 * @param {Array<[string, string|number]>} rows
 */
export function printTable(title, rows) {
  const keyWidth = Math.max(...rows.map(([k]) => k.length), title.length);
  const line = "-".repeat(keyWidth + 12);
  console.log("\n" + line);
  console.log(title);
  console.log(line);
  for (const [k, v] of rows) {
    console.log(`${k.padEnd(keyWidth)}  ${v}`);
  }
  console.log(line);
}

/**
 * Print a reason -> count breakdown with sample details.
 * @param {string} title
 * @param {Array<{reason: string, detail: string}>} entries
 */
export function printReasons(title, entries) {
  if (entries.length === 0) return;
  console.log(`\n${title} (${entries.length}):`);
  /** @type {Map<string, string[]>} */
  const byReason = new Map();
  for (const e of entries) {
    if (!byReason.has(e.reason)) byReason.set(e.reason, []);
    byReason.get(e.reason).push(e.detail);
  }
  for (const [reason, details] of byReason) {
    console.log(`  ${reason}: ${details.length}`);
    for (const d of details) console.log(`    - ${d}`);
  }
}
