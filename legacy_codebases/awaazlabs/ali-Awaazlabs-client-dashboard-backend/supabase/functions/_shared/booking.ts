import { cleanMemberId, str, toBool, toE164, validateDob } from "./validate.ts";

const COMPLETENESS_REASONS = new Set(["missing_first_name", "missing_reason", "missing_appointment"]);

function hasValue(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  return String(value).trim().length > 0;
}

// Recomputes the three completeness review reasons from the FULL merged booking row.
// All other reasons (dob_invalid, recovered_from_analysis, messaging_missing_*, ...) pass through untouched.
export function recomputeReviewState(row: Record<string, unknown>): { needs_review: boolean; review_reasons: string[] } {
  const carried = (Array.isArray(row.review_reasons) ? row.review_reasons : [])
    .filter((reason): reason is string => typeof reason === "string" && reason.length > 0)
    .filter((reason) => !COMPLETENESS_REASONS.has(reason));

  const reasons = [...carried];
  if (!hasValue(row.first_name) && !hasValue(row.full_legal_name)) reasons.push("missing_first_name");
  if (!hasValue(row.reason)) reasons.push("missing_reason");
  if (!hasValue(row.appointment_text) && !hasValue(row.appointment_at)) reasons.push("missing_appointment");

  const review_reasons = Array.from(new Set(reasons));
  return { needs_review: review_reasons.length > 0, review_reasons };
}

/** Retell `call_type` stored under `bookings.raw_payload.call` by retell-webhook / save-booking. */
export function retellCallType(booking: Record<string, unknown>): string | null {
  const raw = booking.raw_payload;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const call = (raw as Record<string, unknown>).call;
  if (!call || typeof call !== "object" || Array.isArray(call)) return null;
  return str((call as Record<string, unknown>).call_type);
}

/**
 * Map a bookings row (+ embedded Retell call metadata) to `appointments.source`.
 * Mirrors scripts/backfill-appointments.js: web_call → web_chat, phone_call → voice.
 */
export function resolveAppointmentSource(
  booking: Record<string, unknown>,
): "voice" | "whatsapp" | "web_chat" | "form" {
  const bookingSource = str(booking.source);
  if (bookingSource === "form") return "form";

  const callType = retellCallType(booking);
  if (callType === "web_call") return "web_chat";
  if (callType === "phone_call") return "voice";
  if (bookingSource === "voice") return "voice";

  return "voice";
}

/** WhatsApp destination: explicit callback, else collected contact when different from caller ID, else caller ID. */
export function resolveWhatsappToNumber(
  booking: { callback_number?: string | null; contact_number?: string | null },
  calledFromNumber?: string | null,
): string {
  const callback = toE164(str(booking.callback_number));
  if (callback) return callback;

  const contact = toE164(str(booking.contact_number));
  const calledFrom = toE164(str(calledFromNumber));
  if (contact && (!calledFrom || contact !== calledFrom)) return contact;

  return calledFrom || contact || "";
}

export function mergeRetellCallPayload(
  existingRaw: unknown,
  call: Record<string, unknown>,
  callId: string,
): Record<string, unknown> {
  const base = existingRaw && typeof existingRaw === "object" && !Array.isArray(existingRaw)
    ? existingRaw as Record<string, unknown>
    : {};
  const existingCall = base.call && typeof base.call === "object" && !Array.isArray(base.call)
    ? base.call as Record<string, unknown>
    : {};
  return {
    ...base,
    call: {
      ...existingCall,
      ...call,
      call_id: callId,
    },
  };
}

export function buildBookingRow(input: Record<string, unknown>, opts: { source: string }) {
  const reasons: string[] = [];

  const dob = validateDob(str(input.dob));
  if (!dob.ok) reasons.push("dob_invalid");
  const subDob = validateDob(str(input.subscriber_dob));
  if (!subDob.ok) reasons.push("subscriber_dob_invalid");

  const first_name = str(input.first_name);
  const reason = str(input.reason);
  const appointment_text = str(input.appointment_text);

  const contact = toE164(str(input.contact_number) ?? str(input.callback_number));

  const row: Record<string, unknown> = {
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
    escalation_trigger: str(input.escalation_trigger) ?? "none",

    needs_review: reasons.length > 0,
    review_reasons: reasons,
  };

  const review = recomputeReviewState({ ...row, appointment_at: input.appointment_at ?? null });
  row.needs_review = review.needs_review;
  row.review_reasons = review.review_reasons;

  const clean: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(row)) {
    if (v !== null && v !== undefined && !(Array.isArray(v) && v.length === 0)) clean[k] = v;
  }
  clean.needs_review = row.needs_review;
  clean.review_reasons = row.review_reasons;
  return clean;
}

export function patientAcct(callId: string): string {
  const tail = (callId || "").replace(/[^a-zA-Z0-9]/g, "").slice(-6).toUpperCase() || "000000";
  return "AWL-" + tail;
}

export function confirmationMessage(p: {
  first_name?: string | null;
  reason?: string | null;
  appointment_text?: string | null;
  patient_status?: string | null;
  insurance_status?: string | null;
  payer_name?: string | null;
  member_id?: string | null;
  intake_method?: string | null;
  assigned_doctor?: string | null;
  language?: string | null;
}): string {
  const name = p.first_name || "there";
  const when = p.appointment_text || "the time we discussed";
  const reason = p.reason || "your cardiology visit";
  const patientStatus = normalizePatientStatus(p.patient_status);
  const insuranceLine = insuranceSummary(p);
  const doc = p.assigned_doctor || "your cardiologist";
  if ((p.language || "en").toLowerCase().startsWith("es")) {
    return [
      "Awaaz Labs Cardiology",
      "",
      `Hola ${name},`,
      "",
      "Resumen de su llamada:",
      `Motivo: ${reason}`,
      `Horario: ${when}`,
      `Paciente: ${patientStatus}`,
      `Seguro: ${insuranceLine}`,
      `Doctor asignado: ${doc}`,
      "",
      "Nuestro equipo dara seguimiento pronto.",
    ].join("\n");
  }
  return [
    "Awaaz Labs Cardiology",
    "",
    `Hi ${name},`,
    "",
    "Call summary:",
    `Reason: ${reason}`,
    `Appointment: ${when}`,
    `Patient status: ${patientStatus}`,
    `Insurance: ${insuranceLine}`,
    `Assigned doctor: ${doc}`,
    "",
    "Our team will follow up shortly.",
  ].join("\n");
}

export function formLinkMessage(
  url: string,
  language?: string | null,
  details?: {
    first_name?: string | null;
    reason?: string | null;
    appointment_text?: string | null;
    patient_status?: string | null;
  }
): string {
  const name = details?.first_name || "there";
  const reason = details?.reason || "your cardiology visit";
  const when = details?.appointment_text || "the time discussed";
  const patientStatus = normalizePatientStatus(details?.patient_status);
  if ((language || "en").toLowerCase().startsWith("es")) {
    return [
      "Awaaz Labs Cardiology",
      "",
      `Hola ${name},`,
      "",
      "Ya tenemos estos detalles de su llamada:",
      `Motivo: ${reason}`,
      `Horario: ${when}`,
      `Paciente: ${patientStatus}`,
      "",
      "Complete sus detalles de seguro y admision aqui:",
      url,
    ].join("\n");
  }
  return [
    "Awaaz Labs Cardiology",
    "",
    `Hi ${name},`,
    "",
    "We already have these details from your call:",
    `Reason: ${reason}`,
    `Appointment: ${when}`,
    `Patient status: ${patientStatus}`,
    "",
    "Please complete your insurance and intake details here:",
    url,
  ].join("\n");
}

export function formSubmittedMessage(p: {
  first_name?: string | null;
  language?: string | null;
}): string {
  const name = p.first_name || "there";
  if ((p.language || "en").toLowerCase().startsWith("es")) {
    return [
      "Awaaz Labs Cardiology",
      "",
      `Hola ${name},`,
      "",
      "Hemos recibido sus detalles de seguro a traves del formulario.",
      "Gracias.",
      "",
      "Nuestro equipo revisara la informacion y dara seguimiento si es necesario.",
    ].join("\n");
  }
  return [
    "Awaaz Labs Cardiology",
    "",
    `Hi ${name},`,
    "",
    "We received your insurance details via the form.",
    "Thank you.",
    "",
    "Our team will review the information and follow up if needed.",
  ].join("\n");
}

function normalizePatientStatus(value?: string | null): string {
  if (!value) return "unknown";
  const v = value.replace(/_/g, " ").trim().toLowerCase();
  if (v === "new") return "new";
  if (v === "existing") return "existing";
  return v;
}

function insuranceSummary(p: {
  intake_method?: string | null;
  insurance_status?: string | null;
  payer_name?: string | null;
  member_id?: string | null;
}): string {
  if (p.intake_method === "form") {
    return "Insurance details will be completed in the secure form.";
  }

  const status = p.insurance_status ? p.insurance_status.replace(/_/g, " ") : "pending";
  const payer = p.payer_name ? ` insurer ${p.payer_name}` : "";
  const member = p.member_id ? `, member ID ${p.member_id}` : "";
  return `${status}${payer}${member}`;
}

const POST_CALL_PROTECTED_FIELDS = new Set([
  "id",
  "created_at",
  "updated_at",
  "call_id",
  "call_started_at",
  "patient_acct",
  "transcript",
  "call_summary",
  "recording_url",
  "raw_payload",
]);

/** Merge Retell `custom_analysis_data` into a bookings row patch. */
export function buildPostCallBookingPatch(
  existing: Record<string, unknown>,
  custom: Record<string, unknown>,
  opts: { overwrite: boolean },
): Record<string, unknown> {
  const input: Record<string, unknown> = {
    ...custom,
    intake_method: custom.intake_method ?? existing.intake_method ?? "voice",
  };
  delete input.contact_number;
  delete input.callback_number;

  let row: Record<string, unknown> = {};
  try {
    row = buildBookingRow(input, { source: "webhook_post_call" });
  } catch (_) {
    return {};
  }

  if (custom.contact_number) row.contact_number = custom.contact_number;
  if (custom.callback_number) row.callback_number = custom.callback_number;

  const patch: Record<string, unknown> = {};
  for (const [field, value] of Object.entries(row)) {
    if (POST_CALL_PROTECTED_FIELDS.has(field)) continue;
    if (value === null || value === undefined || value === "") continue;
    if (!opts.overwrite) {
      const current = existing[field];
      if (current !== null && current !== undefined && current !== "") continue;
    }
    patch[field] = value;
  }
  return patch;
}
