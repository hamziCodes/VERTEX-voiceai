// Backfill: projects bookings (per-call raw capture) + the Retell call dump into
// the normalized appointments layer (patients / appointments / appointment_events /
// confirmation_attempts / audit_events).
//
// IDEMPOTENT: matches on natural keys (bookings.call_id, patient phone+name,
// appointments.booking_id, event labels) and upserts — re-running never duplicates.
// NOTHING fails silently: every skip carries a reason, every DB error is collected
// and reported, and a reconciliation table is printed at the end.
//
// Usage:
//   SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
//     node backfill-appointments.js --calls-file /path/to/retell-all-calls.json

import { readFileSync } from "node:fs";
import { parseAppointmentText } from "./lib/appointment-time.js";
import {
  adminClient, countRows, E164_RE, EMAIL_RE, fetchAll, isBusinessHours,
  nameGarbageReason, normalizeInsuranceStatus, normalizeLanguage, parseArgs,
  printReasons, printTable, str, toBool, toDigits, toE164, validateDob,
  cleanMemberId, TIMEZONE,
} from "./lib/util.js";

// ---------------------------------------------------------------------------
// Port of _shared/booking.ts buildBookingRow (identical semantics; only the
// Deno import is replaced by lib/util.js).
// ---------------------------------------------------------------------------

const COMPLETENESS_REASONS = new Set(["missing_first_name", "missing_reason", "missing_appointment"]);

/** @param {unknown} value */
function hasValue(value) {
  if (value === null || value === undefined) return false;
  return String(value).trim().length > 0;
}

/**
 * @param {Record<string, unknown>} row
 * @returns {{needs_review: boolean, review_reasons: string[]}}
 */
function recomputeReviewState(row) {
  const carried = (Array.isArray(row.review_reasons) ? row.review_reasons : [])
    .filter((reason) => typeof reason === "string" && reason.length > 0)
    .filter((reason) => !COMPLETENESS_REASONS.has(reason));

  const reasons = [...carried];
  if (!hasValue(row.first_name) && !hasValue(row.full_legal_name)) reasons.push("missing_first_name");
  if (!hasValue(row.reason)) reasons.push("missing_reason");
  if (!hasValue(row.appointment_text) && !hasValue(row.appointment_at)) reasons.push("missing_appointment");

  const review_reasons = Array.from(new Set(reasons));
  return { needs_review: review_reasons.length > 0, review_reasons };
}

/**
 * @param {Record<string, unknown>} input custom_analysis_data-shaped object
 * @param {{source: string}} opts
 * @returns {Record<string, unknown>}
 */
function buildBookingRow(input, opts) {
  /** @type {string[]} */
  const reasons = [];

  const dob = validateDob(str(input.dob));
  if (!dob.ok) reasons.push("dob_invalid");
  const subDob = validateDob(str(input.subscriber_dob));
  if (!subDob.ok) reasons.push("subscriber_dob_invalid");

  const first_name = str(input.first_name);
  const reason = str(input.reason);
  const appointment_text = str(input.appointment_text);

  const contact = toE164(str(input.contact_number) ?? str(input.callback_number));

  /** @type {Record<string, unknown>} */
  const row = {
    language: str(input.language),
    contact_number: contact || null,
    whatsapp_suitable: toBool(input.whatsapp_suitable),

    first_name,
    full_legal_name: str(input.full_legal_name),
    dob: dob.value,
    gender: str(input.gender),
    mailing_address: str(input.mailing_address),
    callback_number: toE164(str(input.callback_number)) || null,
    email: str(input.email),

    reason,
    appointment_text,
    patient_status: str(input.patient_status),
    patient_status_unverified: toBool(input.patient_status_unverified) ?? false,

    insurance_status: str(input.insurance_status) ?? "pending",
    payer_name: str(input.payer_name),
    member_id: cleanMemberId(str(input.member_id)),
    group_number: str(input.group_number),
    plan_type: str(input.plan_type),
    payer_id: str(input.payer_id),
    customer_service_number: str(input.customer_service_number),
    provider_name: str(input.provider_name),
    npi: str(input.npi),
    tax_id: str(input.tax_id),
    cpt_codes: str(input.cpt_codes),

    patient_is_subscriber: toBool(input.patient_is_subscriber),
    subscriber_name: str(input.subscriber_name),
    subscriber_dob: subDob.value,
    subscriber_relationship: str(input.subscriber_relationship),
    subscriber_employer: str(input.subscriber_employer),

    has_secondary: toBool(input.has_secondary),
    secondary_payer: str(input.secondary_payer),
    secondary_member_id: cleanMemberId(str(input.secondary_member_id)),
    primary_plan: str(input.primary_plan),
    plan_change_this_year: toBool(input.plan_change_this_year),
    plan_change_details: str(input.plan_change_details),

    referring_provider: str(input.referring_provider),
    prior_auth: toBool(input.prior_auth),
    prior_auth_number: str(input.prior_auth_number),
    seen_other_provider: str(input.seen_other_provider),
    notes: str(input.notes),

    intake_method: str(input.intake_method) ?? "voice",
    source: opts.source,
    triage_flag: str(input.triage_flag) ?? "none",
    transfer_initiated: toBool(input.transfer_initiated) ?? false,

    needs_review: reasons.length > 0,
    review_reasons: reasons,
  };

  const review = recomputeReviewState({ ...row, appointment_at: input.appointment_at ?? null });
  row.needs_review = review.needs_review;
  row.review_reasons = review.review_reasons;

  /** @type {Record<string, unknown>} */
  const clean = {};
  for (const [k, v] of Object.entries(row)) {
    if (v !== null && v !== undefined && !(Array.isArray(v) && v.length === 0)) clean[k] = v;
  }
  clean.needs_review = row.needs_review;
  clean.review_reasons = row.review_reasons;
  return clean;
}

/** Port of _shared/booking.ts patientAcct. @param {string} callId */
function patientAcct(callId) {
  const tail = (callId || "").replace(/[^a-zA-Z0-9]/g, "").slice(-6).toUpperCase() || "000000";
  return "AWL-" + tail;
}

// ---------------------------------------------------------------------------
// Mappings
// ---------------------------------------------------------------------------

/** @type {Record<string, string>} */
const TRIAGE_MAP = {
  none: "none",
  chest_pain_low: "low",
  chest_pain_high: "high",
  urgent_emergency: "urgent",
};

const SANE_TIME_FLOOR_MS = Date.parse("2026-01-01T00:00:00Z"); // appointments_time_sane CHECK

// ---------------------------------------------------------------------------
// Stats / logging accumulators
// ---------------------------------------------------------------------------

/** @type {Array<{reason: string, detail: string}>} */
const bookingSkips = [];
/** @type {Array<{reason: string, detail: string}>} */
const patientSkips = [];
/** @type {Array<{reason: string, detail: string}>} */
const appointmentSkips = [];
/** @type {Array<{reason: string, detail: string}>} */
const warnings = [];
/** @type {Array<{table: string, key: string, error: string}>} */
const dbErrors = [];
/** @type {Array<{name: string, reason: string, bookingIds: string[]}>} */
const rejectedNames = [];

const stats = {
  totalCalls: 0,
  callsWithExtraction: 0,
  callsErrorStatus: 0,
  callsAlreadyInBookings: 0,
  bookingsRecovered: 0,
  bookingsBefore: 0,
  bookingsAfter: 0,
  patientGroups: 0,
  patientsCreated: 0,
  patientsUpdated: 0,
  patientsSkipped: 0,
  patientsRejectedName: 0,
  apptCandidates: 0,
  apptCreated: 0,
  apptUpdated: 0,
  apptUnchanged: 0,
  apptSkipped: 0,
  attemptsCreated: 0,
  eventsCreated: 0,
  auditCreated: 0,
};

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args["calls-file"]) {
    console.error("FATAL: --calls-file <path to retell-all-calls.json> is required.");
    process.exit(1);
  }

  /** @type {any[]} */
  let calls;
  try {
    calls = JSON.parse(readFileSync(args["calls-file"], "utf8"));
  } catch (err) {
    console.error(`FATAL: could not read/parse calls file: ${err instanceof Error ? err.message : err}`);
    process.exit(1);
  }
  if (!Array.isArray(calls)) {
    console.error("FATAL: calls file must be a JSON array of Retell call objects.");
    process.exit(1);
  }
  stats.totalCalls = calls.length;

  const db = adminClient();
  const location = await loadLocation(db);
  console.log(`Location: ${location.name} (${location.timezone}) [${location.id}]`);

  stats.bookingsBefore = await countRows(db, "bookings");
  let bookings = await fetchAll(db, "bookings");
  console.log(`Loaded ${bookings.length} bookings rows, ${calls.length} Retell calls.`);

  // ---- Step 1: recover dump-gap calls into bookings -----------------------
  const recoveredCallIds = await recoverGapBookings(db, calls, bookings);
  stats.bookingsAfter = await countRows(db, "bookings");

  // ---- Step 2: patients ----------------------------------------------------
  const { bookingPatient } = await backfillPatients(db, bookings, location);

  // ---- Step 3: appointments -------------------------------------------------
  await backfillAppointments(db, calls, bookings, bookingPatient, location, recoveredCallIds);

  // ---- Final reconciliation --------------------------------------------------
  report();
  process.exit(dbErrors.length > 0 ? 1 : 0);
}

/** @param {import("@supabase/supabase-js").SupabaseClient} db */
async function loadLocation(db) {
  const { data, error } = await db.from("locations").select("*");
  if (error) {
    console.error(`FATAL: could not load locations: ${error.message}`);
    process.exit(1);
  }
  if (!data || data.length === 0) {
    console.error("FATAL: no locations row found — run the appointments_domain migration first.");
    process.exit(1);
  }
  if (data.length > 1) {
    const named = data.find((l) => l.name === "Awaaz Labs Cardiology");
    if (named) return named;
    console.error(`FATAL: ${data.length} locations found and none named 'Awaaz Labs Cardiology' — cannot pick one.`);
    process.exit(1);
  }
  return data[0];
}

/**
 * Step 1. Inserts a bookings row for every dump call that has non-empty
 * custom_analysis_data, no existing bookings row, and call_status !== 'error'.
 * Mutates `bookings` in place with the inserted rows.
 * @param {import("@supabase/supabase-js").SupabaseClient} db
 * @param {any[]} calls
 * @param {any[]} bookings
 * @returns {Promise<Set<string>>} call_ids recovered in this or a previous run (source backfill_retell)
 */
async function recoverGapBookings(db, calls, bookings) {
  const bookingCallIds = new Set(bookings.map((b) => b.call_id));
  const recovered = new Set(bookings.filter((b) => b.source === "backfill_retell").map((b) => b.call_id));

  for (const call of calls) {
    const callId = str(call.call_id);
    if (!callId) {
      bookingSkips.push({ reason: "call_missing_call_id", detail: "(unidentifiable call object in dump)" });
      continue;
    }
    const custom = call.call_analysis?.custom_analysis_data;
    const hasExtraction = custom && typeof custom === "object" && !Array.isArray(custom) && Object.keys(custom).length > 0;
    if (hasExtraction) stats.callsWithExtraction++;

    if (!hasExtraction) {
      bookingSkips.push({ reason: "no_custom_analysis_data", detail: callId });
      continue;
    }
    if (bookingCallIds.has(callId)) {
      stats.callsAlreadyInBookings++;
      continue; // idempotency: booking already exists (live pipeline or earlier run)
    }
    if (call.call_status === "error") {
      stats.callsErrorStatus++;
      bookingSkips.push({ reason: "call_status_error", detail: callId });
      continue;
    }

    const row = buildBookingRow({ ...custom, intake_method: custom.intake_method ?? "voice" }, { source: "backfill_retell" });
    row.call_id = callId;
    row.patient_acct = patientAcct(callId);
    if (!row.contact_number && str(call.from_number)) row.contact_number = str(call.from_number);
    if (call.start_timestamp) row.call_started_at = new Date(call.start_timestamp).toISOString();
    if (call.transcript) row.transcript = call.transcript;
    if (call.call_analysis?.call_summary) row.call_summary = call.call_analysis.call_summary;
    if (call.recording_url) row.recording_url = call.recording_url;
    row.raw_payload = {
      custom_analysis_data: custom,
      backfill: { call_type: call.call_type ?? null, agent_name: call.agent_name ?? null },
    };

    const { data, error } = await db.from("bookings").insert(row).select("*").single();
    if (error) {
      dbErrors.push({ table: "bookings", key: callId, error: error.message });
      continue;
    }
    stats.bookingsRecovered++;
    bookings.push(data);
    bookingCallIds.add(callId);
    recovered.add(callId);
  }
  return recovered;
}

/**
 * Step 2. Dedup bookings into patients by normalized phone digits + lowercased name.
 * @param {import("@supabase/supabase-js").SupabaseClient} db
 * @param {any[]} bookings
 * @param {any} location
 * @returns {Promise<{bookingPatient: Map<string, string>}>} booking.id -> patient.id
 */
async function backfillPatients(db, bookings, location) {
  /** @type {Map<string, {name: string, phoneE164: string, bookings: any[]}>} */
  const groups = new Map();

  for (const b of bookings) {
    const name = str(b.full_legal_name) ?? str(b.first_name);
    if (!name) {
      patientSkips.push({ reason: "no_usable_name", detail: `booking ${b.id} (call ${b.call_id})` });
      continue;
    }
    if (!str(b.full_legal_name)) {
      warnings.push({ reason: "first_name_used_as_full_name", detail: `booking ${b.id} (call ${b.call_id}): "${name}"` });
    }
    const phoneE164 = toE164(b.contact_number);
    const key = `${toDigits(phoneE164)}|${name.toLowerCase()}`;
    if (!groups.has(key)) groups.set(key, { name, phoneE164, bookings: [] });
    groups.get(key).bookings.push(b);
  }
  stats.patientGroups = groups.size;

  // Idempotent audit trail for rejected names.
  const existingAudits = await fetchAll(db, "audit_events", "id, action, entity, entity_id", "created_at");
  const auditedBookingIds = new Set(
    existingAudits
      .filter((a) => a.action === "backfill_rejected_name" && a.entity === "booking")
      .map((a) => a.entity_id),
  );

  const existingPatients = await fetchAll(db, "patients");
  /** @type {Map<string, any>} */
  const patientsByKey = new Map();
  for (const p of existingPatients) {
    patientsByKey.set(`${toDigits(p.phone_e164)}|${(p.full_legal_name ?? "").toLowerCase()}`, p);
  }

  /** @type {Map<string, string>} */
  const bookingPatient = new Map();

  for (const [key, group] of groups) {
    // Garbage-name gate: never insert what patients_name_not_garbage would reject.
    const garbage = nameGarbageReason(group.name);
    if (garbage) {
      stats.patientsRejectedName++;
      rejectedNames.push({ name: group.name, reason: garbage, bookingIds: group.bookings.map((b) => b.id) });
      for (const b of group.bookings) {
        if (auditedBookingIds.has(b.id)) continue; // audit already written on a previous run
        const { error } = await db.from("audit_events").insert({
          actor: "system:backfill",
          action: "backfill_rejected_name",
          entity: "booking",
          entity_id: b.id,
          metadata: { name: group.name, reason: garbage, call_id: b.call_id },
        });
        if (error) dbErrors.push({ table: "audit_events", key: b.id, error: error.message });
        else stats.auditCreated++;
      }
      continue;
    }

    // Merge group fields: newest booking wins, first non-null per field.
    const sorted = [...group.bookings].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    const pick = (field) => {
      for (const b of sorted) {
        const v = str(b[field]);
        if (v !== null) return v;
      }
      return null;
    };
    const pickBool = (field) => {
      for (const b of sorted) {
        if (b[field] === true || b[field] === false) return b[field];
      }
      return null;
    };

    let phoneE164 = group.phoneE164 || null;
    if (phoneE164 && !E164_RE.test(phoneE164)) {
      warnings.push({ reason: "invalid_phone_dropped", detail: `${key}: "${phoneE164}"` });
      phoneE164 = null;
    }
    let email = pick("email");
    if (email && !EMAIL_RE.test(email)) {
      warnings.push({ reason: "invalid_email_dropped", detail: `${key}: "${email}"` });
      email = null;
    }
    let dob = pick("dob");
    if (dob && !(dob > "1900-01-01" && dob <= new Date().toISOString().slice(0, 10))) {
      warnings.push({ reason: "insane_dob_dropped", detail: `${key}: "${dob}"` });
      dob = null;
    }

    const tokens = group.name.split(/\s+/);
    const patientRow = {
      location_id: location.id,
      full_legal_name: group.name,
      first_name: tokens[0],
      last_name: tokens.length > 1 ? tokens.slice(1).join(" ") : null,
      dob,
      gender: pick("gender"),
      phone_e164: phoneE164,
      whatsapp_suitable: pickBool("whatsapp_suitable"),
      email,
      mailing_address: pick("mailing_address"),
      language: normalizeLanguage(pick("language")),
      payer_name: pick("payer_name"),
      member_id: pick("member_id"),
      group_number: pick("group_number"),
      insurance_status: normalizeInsuranceStatus(pick("insurance_status")),
      is_seeded: false,
    };

    const existing = patientsByKey.get(key);
    let patientId;
    if (existing) {
      // Fill-only-missing update: keeps re-runs idempotent and never clobbers
      // values a human (or the live pipeline) already set.
      /** @type {Record<string, unknown>} */
      const patch = {};
      for (const [field, value] of Object.entries(patientRow)) {
        if (field === "location_id" || field === "is_seeded" || field === "language" || field === "insurance_status") continue;
        if (value === null || value === undefined) continue;
        if (existing[field] === null || existing[field] === undefined || existing[field] === "") patch[field] = value;
      }
      if (Object.keys(patch).length > 0) {
        const { error } = await db.from("patients").update(patch).eq("id", existing.id);
        if (error) {
          dbErrors.push({ table: "patients", key, error: error.message });
          continue;
        }
        stats.patientsUpdated++;
      } else {
        stats.patientsSkipped++;
        patientSkips.push({ reason: "already_exists_no_changes", detail: `patient ${existing.id} ("${group.name}")` });
      }
      patientId = existing.id;
    } else {
      const { data, error } = await db.from("patients").insert(patientRow).select("id").single();
      if (error) {
        dbErrors.push({ table: "patients", key, error: error.message });
        continue;
      }
      stats.patientsCreated++;
      patientId = data.id;
      patientsByKey.set(key, { id: patientId, ...patientRow });
    }

    for (const b of group.bookings) bookingPatient.set(b.id, patientId);
  }

  return { bookingPatient };
}

/**
 * Step 3. One appointment per booking that has appointment_text OR appointment_at.
 * @param {import("@supabase/supabase-js").SupabaseClient} db
 * @param {any[]} calls
 * @param {any[]} bookings
 * @param {Map<string, string>} bookingPatient
 * @param {any} location
 * @param {Set<string>} recoveredCallIds
 */
async function backfillAppointments(db, calls, bookings, bookingPatient, location, recoveredCallIds) {
  const callTypeById = new Map(calls.map((c) => [c.call_id, c.call_type]));

  const existingAppointments = await fetchAll(db, "appointments");
  /** @type {Map<string, any>} */
  const apptByBookingId = new Map(existingAppointments.filter((a) => a.booking_id).map((a) => [a.booking_id, a]));

  const existingEvents = await fetchAll(db, "appointment_events", "id, appointment_id, label", "created_at");
  const eventKeys = new Set(existingEvents.map((e) => `${e.appointment_id}|${e.label}`));

  const existingAttempts = await fetchAll(db, "confirmation_attempts", "id, appointment_id, outcome", "created_at");
  const attemptKeys = new Set(existingAttempts.map((a) => `${a.appointment_id}|${a.outcome}`));

  const tz = location.timezone || TIMEZONE;

  for (const b of bookings) {
    const hasAppt = str(b.appointment_text) !== null || b.appointment_at !== null;
    if (!hasAppt) {
      appointmentSkips.push({ reason: "no_appointment_data", detail: `booking ${b.id} (call ${b.call_id})` });
      continue;
    }
    stats.apptCandidates++;

    const patientId = bookingPatient.get(b.id);
    if (!patientId) {
      stats.apptSkipped++;
      appointmentSkips.push({ reason: "no_patient_for_booking", detail: `booking ${b.id} (call ${b.call_id}) — name missing or rejected` });
      continue;
    }

    const bookedAt = b.call_started_at ?? b.created_at;

    // source: bookings voice/form pass through; everything else resolves via the
    // dump's call_type (web_call -> web_chat, phone_call -> voice).
    let source;
    if (b.source === "voice") source = "voice";
    else if (b.source === "form") source = "form";
    else {
      const callType = callTypeById.get(b.call_id);
      if (callType === "web_call") source = "web_chat";
      else if (callType === "phone_call") source = "voice";
      else {
        source = "voice";
        warnings.push({ reason: "call_type_unknown_defaulted_voice", detail: `booking ${b.id} (call ${b.call_id}, source ${b.source})` });
      }
    }

    let triage = TRIAGE_MAP[str(b.triage_flag) ?? "none"];
    if (triage === undefined) {
      warnings.push({ reason: "unknown_triage_flag_defaulted_none", detail: `booking ${b.id}: "${b.triage_flag}"` });
      triage = "none";
    }

    /** @type {string[]} */
    const reviewReasons = [];
    let serviceInterest = str(b.reason);
    if (!serviceInterest) {
      serviceInterest = "Not captured";
      reviewReasons.push("missing_reason");
    }

    // starts_at: a concrete appointment_at wins; otherwise deterministic parse of
    // appointment_text relative to booked_at in the clinic timezone. Never guess.
    let startsAt = null;
    let parseStatus;
    let parseConfidence;
    if (b.appointment_at) {
      startsAt = new Date(b.appointment_at).toISOString();
      parseStatus = "parsed";
      parseConfidence = "high";
    } else {
      const parsed = parseAppointmentText(b.appointment_text, bookedAt, tz);
      startsAt = parsed.startsAt;
      parseStatus = parsed.status;
      parseConfidence = parsed.confidence;
    }
    // appointments_time_sane CHECK guard: a "parsed" time at/before 2026-01-01 is
    // wrong data, not a real appointment — demote instead of tripping the constraint.
    if (parseStatus === "parsed" && Date.parse(startsAt) <= SANE_TIME_FLOOR_MS) {
      warnings.push({ reason: "parsed_time_before_floor_demoted", detail: `booking ${b.id}: ${startsAt}` });
      startsAt = null;
      parseStatus = "ambiguous";
      parseConfidence = "low";
    }
    if (parseStatus !== "parsed") reviewReasons.push("unparsed_appointment_time");

    const insuranceCaptured = !!(str(b.payer_name) || str(b.member_id));
    const afterHours = !isBusinessHours(new Date(bookedAt), tz);

    const apptRow = {
      location_id: location.id,
      patient_id: patientId,
      booking_id: b.id,
      call_id: b.call_id,
      source,
      service_interest: serviceInterest,
      language: normalizeLanguage(b.language),
      triage,
      insurance_captured: insuranceCaptured,
      booked_by_agent: "receptionist",
      booked_at: new Date(bookedAt).toISOString(),
      after_hours: afterHours,
      starts_at: startsAt,
      appointment_text_raw: str(b.appointment_text),
      time_parse_status: parseStatus,
      time_parse_confidence: parseConfidence,
      needs_review: reviewReasons.length > 0,
      review_reasons: reviewReasons,
      is_seeded: false,
    };

    const existing = apptByBookingId.get(b.id);
    let appointmentId;
    if (existing) {
      // Idempotent update: never touch status here (a human may have progressed the
      // lifecycle; the transition trigger would reject regressions anyway).
      const changed = Object.entries(apptRow).some(([field, value]) => {
        const cur = existing[field];
        if (field === "review_reasons") return JSON.stringify(cur ?? []) !== JSON.stringify(value);
        if (field === "booked_at" || field === "starts_at") {
          const curMs = cur === null ? null : Date.parse(cur);
          const newMs = value === null ? null : Date.parse(value);
          return curMs !== newMs;
        }
        return (cur ?? null) !== (value ?? null);
      });
      if (changed) {
        const { error } = await db.from("appointments").update(apptRow).eq("id", existing.id);
        if (error) {
          dbErrors.push({ table: "appointments", key: b.id, error: error.message });
          continue;
        }
        stats.apptUpdated++;
      } else {
        stats.apptUnchanged++;
      }
      appointmentId = existing.id;
    } else {
      const { data, error } = await db.from("appointments").insert({ ...apptRow, status: "booked" }).select("id").single();
      if (error) {
        dbErrors.push({ table: "appointments", key: b.id, error: error.message });
        continue;
      }
      stats.apptCreated++;
      appointmentId = data.id;
      apptByBookingId.set(b.id, { id: appointmentId, ...apptRow, status: "booked" });
    }

    // Confirmation attempt: a sent WhatsApp confirmation is an outreach that
    // reached the patient; the patient has NOT confirmed, so status stays 'booked'.
    if (b.confirmation_status === "sent" && !attemptKeys.has(`${appointmentId}|reached`)) {
      const { error } = await db.from("confirmation_attempts").insert({
        appointment_id: appointmentId,
        at: b.created_at,
        outcome: "reached",
        channel: str(b.confirmation_channel) ?? "whatsapp",
      });
      if (error) dbErrors.push({ table: "confirmation_attempts", key: b.id, error: error.message });
      else {
        stats.attemptsCreated++;
        attemptKeys.add(`${appointmentId}|reached`);
      }
    }

    // Timeline events (append-only; dedup on appointment_id + label).
    /** @type {Array<{label: string, actor: string, at: string}>} */
    const events = [
      { label: "Booked by AI receptionist (Layla)", actor: "agent:receptionist", at: new Date(bookedAt).toISOString() },
    ];
    if (recoveredCallIds.has(b.call_id)) {
      events.push({ label: "Recovered by backfill", actor: "system:backfill", at: new Date(b.created_at).toISOString() });
    }
    for (const ev of events) {
      const evKey = `${appointmentId}|${ev.label}`;
      if (eventKeys.has(evKey)) continue;
      const { error } = await db.from("appointment_events").insert({
        appointment_id: appointmentId,
        at: ev.at,
        label: ev.label,
        actor: ev.actor,
      });
      if (error) dbErrors.push({ table: "appointment_events", key: `${b.id}/${ev.label}`, error: error.message });
      else {
        stats.eventsCreated++;
        eventKeys.add(evKey);
      }
    }
  }
}

function report() {
  printTable("RECONCILIATION — backfill-appointments", [
    ["Total Retell calls in dump", stats.totalCalls],
    ["Calls with extraction (custom_analysis_data)", stats.callsWithExtraction],
    ["Calls skipped: call_status=error", stats.callsErrorStatus],
    ["Calls already present in bookings", stats.callsAlreadyInBookings],
    ["Bookings recovered from dump (created)", stats.bookingsRecovered],
    ["Bookings rows before / after", `${stats.bookingsBefore} / ${stats.bookingsAfter}`],
    ["Patient identity groups", stats.patientGroups],
    ["Patients created", stats.patientsCreated],
    ["Patients updated (filled missing fields)", stats.patientsUpdated],
    ["Patients skipped (already exist, no change)", stats.patientsSkipped],
    ["Patient groups rejected (garbage name)", stats.patientsRejectedName],
    ["Appointment candidates (text or time present)", stats.apptCandidates],
    ["Appointments created", stats.apptCreated],
    ["Appointments updated", stats.apptUpdated],
    ["Appointments unchanged (idempotent skip)", stats.apptUnchanged],
    ["Appointments skipped", stats.apptSkipped],
    ["Confirmation attempts created", stats.attemptsCreated],
    ["Timeline events created", stats.eventsCreated],
    ["Audit events created (rejected names)", stats.auditCreated],
    ["DB errors (constraint-rejected / failed writes)", dbErrors.length],
  ]);

  if (rejectedNames.length > 0) {
    console.log(`\nREVIEW LIST — names rejected by patients_name_not_garbage (${rejectedNames.length}):`);
    for (const r of rejectedNames) {
      console.log(`  "${r.name}" [${r.reason}] — bookings: ${r.bookingIds.join(", ")}`);
    }
  }

  printReasons("Booking-recovery skips", bookingSkips);
  printReasons("Patient skips", patientSkips);
  printReasons("Appointment skips", appointmentSkips);
  printReasons("Warnings", warnings);

  if (dbErrors.length > 0) {
    console.log(`\nDB ERRORS (${dbErrors.length}) — these rows were NOT written:`);
    for (const e of dbErrors) console.log(`  [${e.table}] ${e.key}: ${e.error}`);
    console.log("\nExiting with code 1 because of the errors above.");
  } else {
    console.log("\nAll writes accounted for. No silent failures.");
  }
}

main().catch((err) => {
  console.error("FATAL:", err);
  process.exit(1);
});
