// Seeds realistic-looking DEMO data into the appointments domain + vob_queue.
//
// - Every patients/appointments row carries is_seeded=true; vob_queue rows are
//   tagged via call_id prefix 'seed_vob_' and raw_payload.seeded=true.
// - DETERMINISTIC: a seeded PRNG (mulberry32, fixed seed) drives every choice,
//   so re-runs with the same --now produce byte-identical data.
// - IDEMPOTENT: appointments/vob rows are keyed on call_id ('seed_appt_001'...),
//   patients on their deterministic phone number; child rows are deduped on
//   natural keys before insert.
// - Every generated row is validated against the schema CHECK constraints
//   BEFORE any insert; the script aborts with a clear message on any violation.
//
// Usage:
//   SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
//     node seed-demo-data.js [--now 2026-07-09T12:00:00Z]

import { addDays, getLocalParts, weekdayOf, zonedTimeToUtc } from "./lib/appointment-time.js";
import {
  adminClient, E164_RE, EMAIL_RE, fetchAll, isBusinessHours,
  nameGarbageReason, parseArgs, printReasons, printTable, TIMEZONE,
} from "./lib/util.js";

// ---------------------------------------------------------------------------
// Distribution parameters (documented; change only deliberately)
// ---------------------------------------------------------------------------

const SEED = 20260709;
const N_BASE_APPTS = 87;   // + 3 recovered-no-show rebooks = 90 appointments
const N_REBOOKS = 3;
const N_VOB = 25;
const N_VOB_LINKED = 15;
const PAST_DAYS = 45;      // appointments spread from now-45d ...
const FUTURE_DAYS = 14;    // ... to now+14d

// Base statuses: past-only terminal states + future-only active states.
// completed 36 (40%), no_show 7 (8%), cancelled 7 (8%)   -> past
// confirmed 18 (20%), booked 13+3 rebooks (17%+), rescheduled 6 (7%) -> future
const PAST_STATUSES = [...rep("completed", 36), ...rep("no_show", 7), ...rep("cancelled", 7)];
const FUTURE_STATUSES = [...rep("confirmed", 18), ...rep("booked", 13), ...rep("rescheduled", 6)];

const SERVICE_INTERESTS = [
  "Palpitations", "Blood pressure concern", "Heart checkup", "Follow-up visit",
  "Chest discomfort", "Arrhythmia consult", "Echocardiogram", "Stress test",
];

const SOURCES = weighted([["voice", 0.70], ["web_chat", 0.15], ["form", 0.10], ["whatsapp", 0.05]]);
const LANGUAGES = weighted([["en", 0.85], ["es", 0.12], ["other", 0.03]]);
const TRIAGES = weighted([["none", 0.82], ["low", 0.10], ["high", 0.06], ["urgent", 0.02]]);
const ATTEMPT_OUTCOMES = weighted([
  ["reached", 0.30], ["voicemail", 0.25], ["confirmed", 0.20],
  ["no_answer", 0.15], ["reschedule_requested", 0.10],
]);

const PAYERS = [
  { name: "Aetna", prefix: "W" },
  { name: "Blue Cross Blue Shield of Illinois", prefix: "XOF" },
  { name: "Cigna", prefix: "U" },
  { name: "UnitedHealthcare", prefix: "9" },
  { name: "Humana", prefix: "H" },
  { name: "Oscar Health", prefix: "OSC" },
  { name: "Medicare", prefix: "1EG" },
];
const INSURED_RATE = 0.85;

const FIRST_NAMES = [
  "James", "Maria", "Robert", "Aisha", "Michael", "Sofia", "David", "Priya",
  "Carlos", "Jennifer", "Wei", "Latoya", "Ahmed", "Emily", "Jose", "Grace",
  "Marcus", "Fatima", "Kevin", "Rosa", "Daniel", "Mei", "Tyrone", "Hannah",
  "Luis", "Nadia", "Brian", "Keisha", "Omar", "Rachel", "Victor", "Amara",
  "Stanislaw", "Yolanda", "Rajesh", "Colleen", "Dmitri", "Esperanza", "Kwame", "Ingrid",
];
const LAST_NAMES = [
  "Johnson", "Garcia", "Smith", "Nguyen", "Williams", "Rodriguez", "Brown", "Patel",
  "Martinez", "Miller", "Chen", "Washington", "Hassan", "Davis", "Hernandez", "Kim",
  "Jackson", "Ali", "Wilson", "Lopez", "Anderson", "Wang", "Robinson", "Goldberg",
  "Torres", "Okafor", "Murphy", "Jefferson", "Farah", "Kowalski", "Ramirez", "Osei",
  "Nowak", "Delgado", "Sharma", "O'Brien", "Volkov", "Reyes", "Mensah", "Larsen",
];
const AREA_CODES = ["312", "773", "847", "708", "630"];
const STREETS = [
  "N Michigan Ave", "W Belmont Ave", "S Halsted St", "N Clark St", "W Devon Ave",
  "S Pulaski Rd", "N Milwaukee Ave", "W 26th St", "N Lincoln Ave", "S Archer Ave",
];
const CHICAGO_AREAS = ["Chicago", "Evanston", "Oak Park", "Cicero", "Skokie", "Berwyn", "Naperville"];
const ZIPS = ["60601", "60614", "60622", "60629", "60640", "60651", "60402", "60201", "60302"];

const NOTE_BODIES = [
  "Patient requested morning slots only.",
  "Prefers Spanish-speaking staff for the visit.",
  "Asked to bring prior EKG records from previous cardiologist.",
  "Verify insurance eligibility before the visit.",
  "Patient may arrive a few minutes late — commuting from the suburbs.",
  "Requested a call the day before as an extra reminder.",
  "Wheelchair access needed at the front entrance.",
];
const NOTE_AUTHORS = ["staff:maria.gonzalez", "staff:james.okafor", "staff:emily.chen"];

const VOB_STATUS_PLAN = [
  // First 15 (linked to appointments) all have complete identities.
  ...rep("verified", 8), ...rep("partial_coverage", 4), ...rep("needs_authorization", 3),
  // Last 10 (unlinked).
  ...rep("not_covered", 2), ...rep("inactive_policy", 2), ...rep("collecting", 3),
  ...rep("missing_information", 3),
];

const VOB_REQUIRED_FIELDS = ["patient_full_name", "patient_dob", "payer_name", "member_id"];

// ---------------------------------------------------------------------------
// Deterministic PRNG (mulberry32)
// ---------------------------------------------------------------------------

/** @param {number} seed @returns {() => number} uniform [0,1) */
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** @param {string} v @param {number} n */
function rep(v, n) { return Array.from({ length: n }, () => v); }

/**
 * @param {Array<[string, number]>} pairs
 * @returns {(rng: () => number) => string}
 */
function weighted(pairs) {
  return (rng) => {
    let r = rng();
    for (const [value, w] of pairs) {
      if ((r -= w) < 0) return value;
    }
    return pairs[pairs.length - 1][0];
  };
}

/** @param {() => number} rng @param {any[]} arr */
function pick(rng, arr) { return arr[Math.floor(rng() * arr.length)]; }

/** @param {() => number} rng @param {number} lo @param {number} hi inclusive */
function randInt(rng, lo, hi) { return lo + Math.floor(rng() * (hi - lo + 1)); }

/** Deterministic in-place Fisher-Yates. @param {() => number} rng @param {any[]} arr */
function shuffle(rng, arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// ---------------------------------------------------------------------------
// Generation helpers
// ---------------------------------------------------------------------------

const MONTH_LABELS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const WEEKDAY_LABELS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

/**
 * Business-hours slot: weekday (Mon-Fri per the locations.business_hours row —
 * sat/sun are null = closed), 08:00-16:30 Chicago wall time on a 15-minute grid.
 * @param {() => number} rng @param {Date} now @param {number} dayOffset
 * @returns {Date} UTC instant
 */
function businessSlot(rng, now, dayOffset) {
  const nowLocal = getLocalParts(now, TIMEZONE);
  let date = addDays({ year: nowLocal.year, month: nowLocal.month, day: nowLocal.day }, dayOffset);
  const wd = weekdayOf(date);
  if (wd === 0) date = addDays(date, dayOffset >= 0 ? 1 : -2); // Sun -> Mon / Fri
  else if (wd === 6) date = addDays(date, dayOffset >= 0 ? 2 : -1); // Sat -> Mon / Fri
  const slot = randInt(rng, 0, 34); // 08:00 .. 16:30 in 15-min steps
  const hour = 8 + Math.floor(slot / 4);
  const minute = (slot % 4) * 15;
  return zonedTimeToUtc(date.year, date.month, date.day, hour, minute, TIMEZONE);
}

/** Human phrasing of an instant, e.g. "Wednesday July 15 at 10:15 AM". @param {Date} d */
function humanizeSlot(d) {
  const p = getLocalParts(d, TIMEZONE);
  const h12 = p.hour % 12 === 0 ? 12 : p.hour % 12;
  const mer = p.hour < 12 ? "AM" : "PM";
  const min = String(p.minute).padStart(2, "0");
  return `${WEEKDAY_LABELS[p.weekday]} ${MONTH_LABELS[p.month - 1]} ${p.day} at ${h12}:${min} ${mer}`;
}

/** @param {() => number} rng @param {number} idx */
function makePhone(rng, idx) {
  return `+1${pick(rng, AREA_CODES)}555${String(100 + idx).padStart(4, "0")}`;
}

/** @param {() => number} rng */
function makeDob(rng) {
  const year = randInt(rng, 1941, 2004);
  const month = randInt(rng, 1, 12);
  const day = randInt(rng, 1, 28);
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/** @param {() => number} rng @param {{prefix: string}} payer */
function makeMemberId(rng, payer) {
  let digits = "";
  for (let i = 0; i < 9; i++) digits += randInt(rng, 0, 9);
  return `${payer.prefix}${digits}`;
}

/** Dollar string with the numeric value recoverable. @param {number} n */
function usd(n) { return `$${n}`; }

/** @param {string|null|undefined} s @returns {number|null} */
function moneyValue(s) {
  if (s === null || s === undefined || s === "") return null;
  const d = String(s).replace(/[^\d]/g, "");
  return d ? parseInt(d, 10) : null;
}

// ---------------------------------------------------------------------------
// Pre-insert validation (mirrors the schema CHECK constraints)
// ---------------------------------------------------------------------------

/** @type {string[]} */
const violations = [];

const APPT_STATUSES = new Set(["booked", "confirmed", "rescheduled", "completed", "cancelled", "no_show"]);
const APPT_SOURCES = new Set(["voice", "whatsapp", "web_chat", "form"]);
const APPT_LANGS = new Set(["en", "es", "other"]);
const APPT_TRIAGES = new Set(["none", "low", "high", "urgent"]);
const APPT_AGENTS = new Set(["receptionist", "vob", "verifier", "chat", "review_taker", "reengagement"]);
const CONF_OUTCOMES = new Set(["reached", "voicemail", "no_answer", "confirmed", "reschedule_requested"]);
const PATIENT_INS = new Set(["covered", "partial", "pending", "pending_form", "unknown", "self_pay"]);
const VOB_STATUSES = new Set([
  "collecting", "in_progress", "verified", "partial_coverage", "needs_authorization",
  "needs_referral", "not_covered", "inactive_policy", "unable_to_verify", "retry_needed",
  "failed_call", "missing_information",
]);

function check(cond, msg) { if (!cond) violations.push(msg); }

function validatePatient(p, key) {
  check(nameGarbageReason(p.full_legal_name) === null, `${key}: name fails patients_name_not_garbage: "${p.full_legal_name}"`);
  check(p.phone_e164 === null || E164_RE.test(p.phone_e164), `${key}: phone not E.164: "${p.phone_e164}"`);
  check(p.email === null || EMAIL_RE.test(p.email), `${key}: bad email: "${p.email}"`);
  check(p.dob === null || (p.dob > "1900-01-01" && p.dob <= new Date().toISOString().slice(0, 10)), `${key}: dob out of range: ${p.dob}`);
  check(APPT_LANGS.has(p.language), `${key}: bad language: ${p.language}`);
  check(PATIENT_INS.has(p.insurance_status), `${key}: bad insurance_status: ${p.insurance_status}`);
}

function validateAppointment(a, key) {
  check(APPT_STATUSES.has(a.status), `${key}: bad status: ${a.status}`);
  check(APPT_SOURCES.has(a.source), `${key}: bad source: ${a.source}`);
  check(APPT_LANGS.has(a.language), `${key}: bad language: ${a.language}`);
  check(APPT_TRIAGES.has(a.triage), `${key}: bad triage: ${a.triage}`);
  check(APPT_AGENTS.has(a.booked_by_agent), `${key}: bad booked_by_agent: ${a.booked_by_agent}`);
  check(typeof a.service_interest === "string" && a.service_interest.length > 0, `${key}: empty service_interest`);
  check(a.time_parse_status !== "parsed" || a.starts_at !== null, `${key}: parsed without starts_at`);
  check(a.starts_at === null || Date.parse(a.starts_at) > Date.parse("2026-01-01T00:00:00Z"), `${key}: starts_at before appointments_time_sane floor (2026-01-01) — is --now too early?`);
}

function validateAttempt(c, key) {
  check(CONF_OUTCOMES.has(c.outcome), `${key}: bad outcome: ${c.outcome}`);
}

function validateVob(v, key) {
  check(VOB_STATUSES.has(v.status), `${key}: bad vob status: ${v.status}`);
  check(v.member_id === null || /^[A-Za-z0-9-]{2,40}$/.test(v.member_id), `${key}: bad member_id: ${v.member_id}`);
  check(v.patient_dob === null || /^\d{4}-\d{2}-\d{2}$/.test(v.patient_dob), `${key}: bad patient_dob: ${v.patient_dob}`);
  for (const kind of ["individual_deductible", "family_deductible", "individual_oop", "family_oop"]) {
    const total = moneyValue(v[`${kind}_total`]);
    const met = moneyValue(v[`${kind}_met`]);
    const remaining = moneyValue(v[`${kind}_remaining`]);
    if (total !== null || met !== null || remaining !== null) {
      check(total !== null && met !== null && remaining !== null, `${key}: ${kind} partially filled`);
      if (total !== null && met !== null && remaining !== null) {
        check(met + remaining === total, `${key}: ${kind} met(${met}) + remaining(${remaining}) != total(${total})`);
      }
    }
  }
  // queue readiness must agree with the live logic's required-field rule
  const missing = VOB_REQUIRED_FIELDS.filter((f) => !v[f]);
  if (!v.provider_name && !v.practice_name) missing.push("provider_name_or_practice_name");
  check(v.queue_ready === (missing.length === 0), `${key}: queue_ready=${v.queue_ready} but missing=[${missing.join(",")}]`);
  check(JSON.stringify(v.missing_required_fields) === JSON.stringify(missing), `${key}: missing_required_fields mismatch`);
}

// ---------------------------------------------------------------------------
// Generation
// ---------------------------------------------------------------------------

/**
 * @param {Date} now
 * @returns {{specs: any[], vobs: any[]}}
 */
function generate(now) {
  const rng = mulberry32(SEED);
  const nowMs = now.getTime();

  const pastStatuses = shuffle(rng, [...PAST_STATUSES]);
  const futureStatuses = shuffle(rng, [...FUTURE_STATUSES]);

  // Unique deterministic patient names.
  const usedNames = new Set();
  const nextName = () => {
    for (let tries = 0; tries < 100; tries++) {
      const first = pick(rng, FIRST_NAMES);
      const last = pick(rng, LAST_NAMES);
      const full = `${first} ${last}`;
      if (!usedNames.has(full)) {
        usedNames.add(full);
        return { first, last, full };
      }
    }
    throw new Error("could not generate a unique name (name pool exhausted)");
  };

  /** @type {any[]} */
  const specs = []; // one per appointment: { patient, appointment, attempts, events, note }

  for (let i = 0; i < N_BASE_APPTS; i++) {
    const isPast = i < pastStatuses.length;
    const status = isPast ? pastStatuses[i] : futureStatuses[i - pastStatuses.length];
    const callId = `seed_appt_${String(i + 1).padStart(3, "0")}`;

    const name = nextName();
    const dayOffset = isPast ? -randInt(rng, 1, PAST_DAYS) : randInt(rng, 1, FUTURE_DAYS);
    const startsAt = businessSlot(rng, now, dayOffset);

    // booked_at is always in the past; a slice of bookings happens after hours.
    let bookedAtMs;
    if (isPast) {
      bookedAtMs = startsAt.getTime() - randInt(rng, 1, 10) * 86_400_000 - randInt(rng, 0, 20) * 3_600_000;
    } else {
      bookedAtMs = nowMs - randInt(rng, 1, 10) * 86_400_000 - randInt(rng, 0, 20) * 3_600_000;
    }
    const bookedAt = new Date(bookedAtMs);

    const language = LANGUAGES(rng);
    const insured = rng() < INSURED_RATE;
    const payer = insured ? pick(rng, PAYERS) : null;
    const memberId = payer ? makeMemberId(rng, payer) : null;
    const phone = makePhone(rng, i);
    const whatsapp = rng() < 0.65;
    const hasEmail = rng() < 0.6;

    const patient = {
      full_legal_name: name.full,
      first_name: name.first,
      last_name: name.last,
      dob: makeDob(rng),
      gender: rng() < 0.5 ? "female" : "male",
      phone_e164: phone,
      whatsapp_suitable: whatsapp,
      email: hasEmail ? `${name.first.toLowerCase()}.${name.last.toLowerCase().replace(/[^a-z]/g, "")}${i}@example.com` : null,
      mailing_address: `${randInt(rng, 100, 9899)} ${pick(rng, STREETS)}, ${pick(rng, CHICAGO_AREAS)}, IL ${pick(rng, ZIPS)}`,
      language,
      payer_name: payer ? payer.name : null,
      member_id: memberId,
      group_number: payer && rng() < 0.5 ? `GRP${randInt(rng, 10000, 99999)}` : null,
      insurance_status: insured ? (rng() < 0.6 ? "covered" : "pending") : (rng() < 0.5 ? "self_pay" : "unknown"),
      is_seeded: true,
    };

    const appointment = {
      call_id: callId,
      status,
      source: SOURCES(rng),
      service_interest: pick(rng, SERVICE_INTERESTS),
      language,
      triage: TRIAGES(rng),
      insurance_captured: insured,
      booked_by_agent: "receptionist",
      booked_at: bookedAt.toISOString(),
      after_hours: !isBusinessHours(bookedAt, TIMEZONE),
      starts_at: startsAt.toISOString(),
      appointment_text_raw: humanizeSlot(startsAt),
      time_parse_status: "parsed",
      time_parse_confidence: "high",
      needs_review: false,
      review_reasons: [],
      is_seeded: true,
    };

    // Confirmation attempts: older appointments accumulate more attempts.
    const nAttempts = isPast ? randInt(rng, 1, 3) : randInt(rng, 0, 2);
    const attempts = [];
    const horizonMs = Math.min(startsAt.getTime(), nowMs) - bookedAtMs;
    for (let k = 0; k < nAttempts; k++) {
      const frac = (k + 1) / (nAttempts + 1);
      const at = new Date(bookedAtMs + Math.max(3_600_000, Math.floor(horizonMs * frac)));
      attempts.push({ at: at.toISOString(), outcome: ATTEMPT_OUTCOMES(rng), channel: whatsapp ? "whatsapp" : "sms" });
    }
    if (status === "confirmed" && attempts.length === 0) {
      attempts.push({ at: new Date(bookedAtMs + Math.max(3_600_000, Math.floor(horizonMs / 2))).toISOString(), outcome: "confirmed", channel: whatsapp ? "whatsapp" : "sms" });
    }
    if (status === "confirmed") attempts[attempts.length - 1].outcome = "confirmed";
    if (status === "rescheduled" && attempts.length > 0) attempts[attempts.length - 1].outcome = "reschedule_requested";

    // Timeline events.
    const events = [
      { at: bookedAt.toISOString(), label: "Booked by AI receptionist (Layla)", actor: "agent:receptionist" },
      ...attempts.map((a, k) => ({ at: a.at, label: `Reminder sent via ${a.channel === "whatsapp" ? "WhatsApp" : "SMS"} (attempt ${k + 1})`, actor: "agent:verifier" })),
    ];
    if (status === "confirmed") {
      events.push({ at: attempts[attempts.length - 1].at, label: "Confirmed by patient", actor: "patient" });
    } else if (status === "completed") {
      events.push({ at: new Date(startsAt.getTime() + 30 * 60_000).toISOString(), label: "Visit completed", actor: "staff:frontdesk" });
    } else if (status === "no_show") {
      events.push({ at: new Date(startsAt.getTime() + 60 * 60_000).toISOString(), label: "Marked as no-show", actor: "staff:frontdesk" });
    } else if (status === "cancelled") {
      events.push({ at: new Date(Math.min(startsAt.getTime(), nowMs) - 12 * 3_600_000).toISOString(), label: "Cancelled by patient", actor: "patient" });
    } else if (status === "rescheduled") {
      events.push({ at: attempts.length > 0 ? attempts[attempts.length - 1].at : bookedAt.toISOString(), label: "Reschedule requested by patient", actor: "patient" });
    }

    const note = rng() < 0.2
      ? { at: new Date(bookedAtMs + 2 * 3_600_000).toISOString(), author: pick(rng, NOTE_AUTHORS), body: pick(rng, NOTE_BODIES) }
      : null;

    specs.push({ callId, patient, appointment, attempts, events, note, rebookOf: null });
  }

  // Recovered no-show pattern: N_REBOOKS no_show patients get a later re-booked
  // appointment (drives the "recovered revenue" metric on the dashboard).
  const noShows = specs.filter((s) => s.appointment.status === "no_show").slice(0, N_REBOOKS);
  noShows.forEach((orig, j) => {
    const i = N_BASE_APPTS + j;
    const callId = `seed_appt_${String(i + 1).padStart(3, "0")}`;
    const startsAt = businessSlot(rng, now, randInt(rng, 3, FUTURE_DAYS));
    const bookedAt = new Date(nowMs - randInt(rng, 1, 4) * 86_400_000 - randInt(rng, 0, 20) * 3_600_000);
    specs.push({
      callId,
      patient: orig.patient, // same person — appointment reuses the original patient row
      appointment: {
        call_id: callId,
        status: "booked",
        source: "voice",
        service_interest: orig.appointment.service_interest,
        language: orig.appointment.language,
        triage: "none",
        insurance_captured: orig.appointment.insurance_captured,
        booked_by_agent: "reengagement",
        booked_at: bookedAt.toISOString(),
        after_hours: !isBusinessHours(bookedAt, TIMEZONE),
        starts_at: startsAt.toISOString(),
        appointment_text_raw: humanizeSlot(startsAt),
        time_parse_status: "parsed",
        time_parse_confidence: "high",
        needs_review: false,
        review_reasons: [],
        is_seeded: true,
      },
      attempts: [],
      events: [
        { at: bookedAt.toISOString(), label: "Recovered no-show: re-booked by re-engagement agent", actor: "agent:reengagement" },
      ],
      note: null,
      rebookOf: orig.callId,
    });
  });

  // ---- VOB worksheets -------------------------------------------------------
  // First N_VOB_LINKED link to insured seeded appointments with EXACT identity match.
  const linkable = specs.filter((s) => s.patient.payer_name && s.patient.member_id && !s.rebookOf).slice(0, N_VOB_LINKED);
  if (linkable.length < N_VOB_LINKED) {
    throw new Error(`only ${linkable.length} insured appointments available to link (need ${N_VOB_LINKED})`);
  }

  /** @type {any[]} */
  const vobs = [];
  for (let i = 0; i < N_VOB; i++) {
    const status = VOB_STATUS_PLAN[i];
    const callId = `seed_vob_${String(i + 1).padStart(3, "0")}`;
    const linked = i < N_VOB_LINKED ? linkable[i] : null;

    let identity;
    if (linked) {
      identity = {
        patient_full_name: linked.patient.full_legal_name,
        patient_dob: linked.patient.dob,
        payer_name: linked.patient.payer_name,
        member_id: linked.patient.member_id,
      };
    } else {
      const name = nextName();
      const payer = pick(rng, PAYERS);
      identity = {
        patient_full_name: name.full,
        patient_dob: makeDob(rng),
        payer_name: payer.name,
        member_id: makeMemberId(rng, payer),
      };
    }

    const queuedAt = new Date(nowMs - randInt(rng, 1, 30) * 86_400_000);
    const v = {
      call_id: callId,
      status,
      queued_at: queuedAt.toISOString(),
      last_extracted_at: queuedAt.toISOString(),
      practice_name: "Awaaz Labs Cardiology",
      provider_name: "Dr. Adeel Rahman",
      service_type: pick(rng, SERVICE_INTERESTS),
      cpt_codes: pick(rng, ["99203", "99213", "93000", "93306", "93015"]),
      ...identity,
      policy_active: null, plan_type: null, effective_date: null, network_status: null,
      individual_deductible_total: null, individual_deductible_met: null, individual_deductible_remaining: null,
      family_deductible_total: null, family_deductible_met: null, family_deductible_remaining: null,
      individual_oop_total: null, individual_oop_met: null, individual_oop_remaining: null,
      family_oop_total: null, family_oop_met: null, family_oop_remaining: null,
      copay: null, coinsurance: null, deductible_applies: null,
      cpt_coverage: null, cpt_limitations: null,
      prior_auth_required: null, auth_method: null, referral_required: null,
      representative_name: null, call_reference_number: null, notes: null,
      needs_review: false,
      review_reasons: [],
      raw_payload: { seeded: true, generator: "seed-demo-data", seed: SEED },
      _linkedCallId: linked ? linked.callId : null,
    };

    const fillBenefits = () => {
      const dedTotal = randInt(rng, 2, 20) * 250; // $500-$5000
      const dedMet = randInt(rng, 0, dedTotal / 50) * 50;
      const famTotal = dedTotal * randInt(rng, 2, 3);
      const famMet = randInt(rng, 0, famTotal / 50) * 50;
      const oopTotal = randInt(rng, 8, 32) * 250; // $2000-$8000
      const oopMet = randInt(rng, 0, oopTotal / 50) * 50;
      const famOopTotal = oopTotal * 2;
      const famOopMet = randInt(rng, 0, famOopTotal / 50) * 50;
      Object.assign(v, {
        policy_active: "Yes",
        plan_type: pick(rng, ["PPO", "HMO", "EPO", "POS"]),
        effective_date: "2026-01-01",
        network_status: "In network",
        individual_deductible_total: usd(dedTotal),
        individual_deductible_met: usd(dedMet),
        individual_deductible_remaining: usd(dedTotal - dedMet),
        family_deductible_total: usd(famTotal),
        family_deductible_met: usd(famMet),
        family_deductible_remaining: usd(famTotal - famMet),
        individual_oop_total: usd(oopTotal),
        individual_oop_met: usd(oopMet),
        individual_oop_remaining: usd(oopTotal - oopMet),
        family_oop_total: usd(famOopTotal),
        family_oop_met: usd(famOopMet),
        family_oop_remaining: usd(famOopTotal - famOopMet),
        copay: usd(randInt(rng, 4, 12) * 5), // $20-$60
        coinsurance: `${pick(rng, [10, 20, 30])}%`,
        deductible_applies: "Yes",
        cpt_coverage: "Covered",
        prior_auth_required: "No",
        referral_required: "No",
        representative_name: pick(rng, ["Denise", "Marcus", "Angela", "Trevor", "Simone"]),
        call_reference_number: `REF-${randInt(rng, 100000, 999999)}`,
      });
    };

    if (status === "verified") {
      fillBenefits();
      v.notes = "Benefits verified with payer representative.";
    } else if (status === "partial_coverage") {
      fillBenefits();
      v.cpt_coverage = "Partial";
      v.cpt_limitations = "Diagnostic imaging covered at 50% until deductible met.";
      v.notes = "Partial coverage for requested CPT codes.";
      v.review_reasons = ["vob_status_partial_coverage"];
      v.needs_review = true;
    } else if (status === "needs_authorization") {
      fillBenefits();
      v.prior_auth_required = "Yes";
      v.auth_method = "Payer portal";
      v.notes = "Prior authorization required before scheduling the procedure.";
      v.review_reasons = ["vob_status_needs_authorization"];
      v.needs_review = true;
    } else if (status === "not_covered") {
      v.policy_active = "Yes";
      v.plan_type = pick(rng, ["PPO", "HMO"]);
      v.cpt_coverage = "Not covered";
      v.notes = "Requested service is excluded under the current plan.";
      v.review_reasons = ["vob_status_not_covered"];
      v.needs_review = true;
    } else if (status === "inactive_policy") {
      v.policy_active = "No";
      v.notes = "Policy terminated; patient should contact payer.";
      v.review_reasons = ["vob_status_inactive_policy"];
      v.needs_review = true;
    } else if (status === "collecting") {
      // required identity complete, benefits not yet captured — ready for the queue
    } else if (status === "missing_information") {
      // deterministically drop required fields so queue_ready=false
      v.member_id = null;
      if (i % 2 === 0) v.patient_dob = null;
      v.review_reasons = ["vob_status_missing_information"];
      v.needs_review = true;
    }

    // Queue readiness per the live transcript-vob-poc logic.
    const missing = VOB_REQUIRED_FIELDS.filter((f) => !v[f]);
    if (!v.provider_name && !v.practice_name) missing.push("provider_name_or_practice_name");
    v.queue_ready = missing.length === 0;
    v.missing_required_fields = missing;
    v.ready_at = v.queue_ready ? v.queued_at : null;
    vobs.push(v);
  }

  // priority_position: sequential over ready rows, in call_id order.
  let pos = 0;
  for (const v of vobs) v.priority_position = v.queue_ready ? ++pos : null;

  return { specs, vobs };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const stats = {
  patientsCreated: 0, patientsUpdated: 0, patientsSkipped: 0,
  apptCreated: 0, apptUpdated: 0, apptSkipped: 0,
  attemptsCreated: 0, attemptsSkipped: 0,
  eventsCreated: 0, eventsSkipped: 0,
  notesCreated: 0, notesSkipped: 0,
  vobCreated: 0, vobUpdated: 0,
  linksSet: 0, linksVerified: 0,
};
/** @type {Array<{reason: string, detail: string}>} */
const warnings = [];
/** @type {Array<{table: string, key: string, error: string}>} */
const dbErrors = [];

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const now = args.now ? new Date(args.now) : new Date();
  if (isNaN(now.getTime())) {
    console.error(`FATAL: could not parse --now value "${args.now}"`);
    process.exit(1);
  }
  console.log(`Seeding relative to now = ${now.toISOString()} (seed ${SEED})`);

  const { specs, vobs } = generate(now);

  // ---- Validate EVERYTHING before touching the database --------------------
  const patientByPhone = new Map();
  for (const s of specs) patientByPhone.set(s.patient.phone_e164, s.patient);
  for (const [phone, p] of patientByPhone) validatePatient(p, `patient ${phone} (${p.full_legal_name})`);
  for (const s of specs) {
    validateAppointment(s.appointment, s.callId);
    for (const a of s.attempts) validateAttempt(a, `${s.callId} attempt`);
  }
  for (const v of vobs) validateVob(v, v.call_id);
  if (violations.length > 0) {
    console.error(`\nABORTING — ${violations.length} generated row(s) violate schema constraints. Nothing was written.`);
    for (const v of violations) console.error("  " + v);
    process.exit(1);
  }
  console.log(`Validated ${patientByPhone.size} patients, ${specs.length} appointments, ${vobs.length} VOB rows against schema constraints.`);

  const db = adminClient();
  const location = await loadLocation(db);
  console.log(`Location: ${location.name} (${location.timezone}) [${location.id}]`);

  // ---- Patients (keyed on deterministic phone) ------------------------------
  const existingPatients = await fetchAll(db, "patients");
  const existingByPhone = new Map(existingPatients.filter((p) => p.phone_e164).map((p) => [p.phone_e164, p]));
  /** @type {Map<string, string>} phone -> patient id */
  const patientIds = new Map();

  for (const [phone, p] of patientByPhone) {
    const row = { ...p, location_id: location.id };
    const existing = existingByPhone.get(phone);
    if (existing) {
      const changed = Object.entries(row).some(([f, val]) => (existing[f] ?? null) !== (val ?? null));
      if (changed) {
        const { error } = await db.from("patients").update(row).eq("id", existing.id);
        if (error) { dbErrors.push({ table: "patients", key: phone, error: error.message }); continue; }
        stats.patientsUpdated++;
      } else {
        stats.patientsSkipped++;
      }
      patientIds.set(phone, existing.id);
    } else {
      const { data, error } = await db.from("patients").insert(row).select("id").single();
      if (error) { dbErrors.push({ table: "patients", key: phone, error: error.message }); continue; }
      stats.patientsCreated++;
      patientIds.set(phone, data.id);
    }
  }

  // ---- Appointments (keyed on call_id) --------------------------------------
  const existingAppts = await fetchAll(db, "appointments");
  const apptByCallId = new Map(existingAppts.filter((a) => a.call_id).map((a) => [a.call_id, a]));
  /** @type {Map<string, string>} callId -> appointment id */
  const apptIds = new Map();

  for (const s of specs) {
    const patientId = patientIds.get(s.patient.phone_e164);
    if (!patientId) {
      warnings.push({ reason: "appointment_skipped_no_patient", detail: s.callId });
      stats.apptSkipped++;
      continue;
    }
    const row = { ...s.appointment, location_id: location.id, patient_id: patientId };
    const existing = apptByCallId.get(s.callId);
    if (existing) {
      // Never update status on an existing row: the DB transition trigger forbids
      // regressions and a demo re-run must not fight it. Warn when they diverge.
      const { status: targetStatus, ...rest } = row;
      if (existing.status !== targetStatus) {
        warnings.push({ reason: "status_divergence_left_untouched", detail: `${s.callId}: db=${existing.status} seed=${targetStatus}` });
      }
      const changed = Object.entries(rest).some(([f, val]) => {
        if (f === "review_reasons") return JSON.stringify(existing[f] ?? []) !== JSON.stringify(val);
        if (f === "booked_at" || f === "starts_at") return Date.parse(existing[f]) !== Date.parse(val);
        return (existing[f] ?? null) !== (val ?? null);
      });
      if (changed) {
        const { error } = await db.from("appointments").update(rest).eq("id", existing.id);
        if (error) { dbErrors.push({ table: "appointments", key: s.callId, error: error.message }); continue; }
        stats.apptUpdated++;
      } else {
        stats.apptSkipped++;
      }
      apptIds.set(s.callId, existing.id);
    } else {
      const { data, error } = await db.from("appointments").insert(row).select("id").single();
      if (error) { dbErrors.push({ table: "appointments", key: s.callId, error: error.message }); continue; }
      stats.apptCreated++;
      apptIds.set(s.callId, data.id);
    }
  }

  // ---- Child rows (attempts / events / notes), deduped on natural keys ------
  const existingAttempts = await fetchAll(db, "confirmation_attempts", "id, appointment_id, at, outcome", "created_at");
  const attemptKeys = new Set(existingAttempts.map((a) => `${a.appointment_id}|${Date.parse(a.at)}|${a.outcome}`));
  const existingEvents = await fetchAll(db, "appointment_events", "id, appointment_id, label", "created_at");
  const eventKeys = new Set(existingEvents.map((e) => `${e.appointment_id}|${e.label}`));
  const existingNotes = await fetchAll(db, "staff_notes", "id, appointment_id, body", "created_at");
  const noteKeys = new Set(existingNotes.map((n) => `${n.appointment_id}|${n.body}`));

  for (const s of specs) {
    const apptId = apptIds.get(s.callId);
    if (!apptId) continue;

    for (const a of s.attempts) {
      const key = `${apptId}|${Date.parse(a.at)}|${a.outcome}`;
      if (attemptKeys.has(key)) { stats.attemptsSkipped++; continue; }
      const { error } = await db.from("confirmation_attempts").insert({ appointment_id: apptId, ...a });
      if (error) dbErrors.push({ table: "confirmation_attempts", key: s.callId, error: error.message });
      else { stats.attemptsCreated++; attemptKeys.add(key); }
    }

    for (const e of s.events) {
      const key = `${apptId}|${e.label}`;
      if (eventKeys.has(key)) { stats.eventsSkipped++; continue; }
      const { error } = await db.from("appointment_events").insert({ appointment_id: apptId, ...e });
      if (error) dbErrors.push({ table: "appointment_events", key: `${s.callId}/${e.label}`, error: error.message });
      else { stats.eventsCreated++; eventKeys.add(key); }
    }

    if (s.note) {
      const key = `${apptId}|${s.note.body}`;
      if (noteKeys.has(key)) { stats.notesSkipped++; }
      else {
        const { error } = await db.from("staff_notes").insert({ appointment_id: apptId, ...s.note });
        if (error) dbErrors.push({ table: "staff_notes", key: s.callId, error: error.message });
        else { stats.notesCreated++; noteKeys.add(key); }
      }
    }
  }

  // ---- VOB queue (upsert on unique call_id) ----------------------------------
  const { data: existingVobs, error: vobFetchErr } = await db.from("vob_queue").select("call_id").like("call_id", "seed_vob_%");
  if (vobFetchErr) { console.error("FATAL: could not read vob_queue:", vobFetchErr.message); process.exit(1); }
  const existingVobIds = new Set((existingVobs ?? []).map((v) => v.call_id));

  /** @type {Map<string, string>} vob call_id -> vob uuid */
  const vobIds = new Map();
  for (const v of vobs) {
    const { _linkedCallId, ...row } = v;
    const wasExisting = existingVobIds.has(v.call_id);
    const { data, error } = await db.from("vob_queue").upsert(row, { onConflict: "call_id" }).select("id").single();
    if (error) { dbErrors.push({ table: "vob_queue", key: v.call_id, error: error.message }); continue; }
    vobIds.set(v.call_id, data.id);
    if (wasExisting) stats.vobUpdated++; else stats.vobCreated++;
  }

  // ---- Link appointments.vob_id and VERIFY identity match --------------------
  for (const v of vobs) {
    if (!v._linkedCallId) continue;
    const apptId = apptIds.get(v._linkedCallId);
    const vobId = vobIds.get(v.call_id);
    if (!apptId || !vobId) {
      warnings.push({ reason: "vob_link_skipped", detail: `${v.call_id} -> ${v._linkedCallId} (row missing)` });
      continue;
    }
    const { error } = await db.from("appointments").update({ vob_id: vobId }).eq("id", apptId);
    if (error) { dbErrors.push({ table: "appointments(vob_id)", key: v.call_id, error: error.message }); continue; }
    stats.linksSet++;
  }

  // Verification pass: every linked pair must agree on patient identity + payer.
  const { data: linkedRows, error: verifyErr } = await db
    .from("appointments")
    .select("call_id, vob_id, patients(full_legal_name, dob, payer_name, member_id), vob_queue:vob_id(call_id, patient_full_name, patient_dob, payer_name, member_id)")
    .like("call_id", "seed_appt_%")
    .not("vob_id", "is", null);
  if (verifyErr) {
    console.error("FATAL: link verification query failed:", verifyErr.message);
    process.exit(1);
  }
  /** @type {string[]} */
  const linkMismatches = [];
  for (const r of linkedRows ?? []) {
    const before = linkMismatches.length;
    const p = r.patients;
    const v = r.vob_queue;
    if (!p || !v) {
      linkMismatches.push(`${r.call_id}: orphan join (patient or vob row missing)`);
    } else {
      if (p.full_legal_name !== v.patient_full_name) linkMismatches.push(`${r.call_id}: name "${p.full_legal_name}" != "${v.patient_full_name}"`);
      if (p.dob !== v.patient_dob) linkMismatches.push(`${r.call_id}: dob ${p.dob} != ${v.patient_dob}`);
      if (p.payer_name !== v.payer_name) linkMismatches.push(`${r.call_id}: payer "${p.payer_name}" != "${v.payer_name}"`);
      if (p.member_id !== v.member_id) linkMismatches.push(`${r.call_id}: member_id ${p.member_id} != ${v.member_id}`);
    }
    if (linkMismatches.length === before) stats.linksVerified++;
  }

  // ---- Report ----------------------------------------------------------------
  printTable("SEED REPORT — seed-demo-data", [
    ["Seed / now", `${SEED} / ${now.toISOString()}`],
    ["Patients created / updated / unchanged", `${stats.patientsCreated} / ${stats.patientsUpdated} / ${stats.patientsSkipped}`],
    ["Appointments created / updated / unchanged", `${stats.apptCreated} / ${stats.apptUpdated} / ${stats.apptSkipped}`],
    ["Confirmation attempts created / deduped", `${stats.attemptsCreated} / ${stats.attemptsSkipped}`],
    ["Timeline events created / deduped", `${stats.eventsCreated} / ${stats.eventsSkipped}`],
    ["Staff notes created / deduped", `${stats.notesCreated} / ${stats.notesSkipped}`],
    ["VOB rows created / updated", `${stats.vobCreated} / ${stats.vobUpdated}`],
    ["Appointment->VOB links set / verified", `${stats.linksSet} / ${stats.linksVerified}`],
    ["Link identity mismatches", linkMismatches.length],
    ["DB errors", dbErrors.length],
  ]);

  printReasons("Warnings", warnings);

  if (linkMismatches.length > 0) {
    console.error(`\nLINK VERIFICATION FAILED (${linkMismatches.length}):`);
    for (const m of linkMismatches) console.error("  " + m);
  }
  if (dbErrors.length > 0) {
    console.error(`\nDB ERRORS (${dbErrors.length}) — these rows were NOT written:`);
    for (const e of dbErrors) console.error(`  [${e.table}] ${e.key}: ${e.error}`);
  }

  const failed = dbErrors.length > 0 || linkMismatches.length > 0;
  console.log(failed ? "\nCompleted WITH ERRORS — see above." : "\nAll writes accounted for. No silent failures.");
  process.exit(failed ? 1 : 0);
}

/** @param {import("@supabase/supabase-js").SupabaseClient} db */
async function loadLocation(db) {
  const { data, error } = await db.from("locations").select("*");
  if (error) { console.error(`FATAL: could not load locations: ${error.message}`); process.exit(1); }
  if (!data || data.length === 0) { console.error("FATAL: no locations row — run migrations first."); process.exit(1); }
  const named = data.find((l) => l.name === "Awaaz Labs Cardiology");
  if (data.length > 1 && !named) { console.error(`FATAL: ${data.length} locations and none named 'Awaaz Labs Cardiology'.`); process.exit(1); }
  return named ?? data[0];
}

main().catch((err) => {
  console.error("FATAL:", err);
  process.exit(1);
});
