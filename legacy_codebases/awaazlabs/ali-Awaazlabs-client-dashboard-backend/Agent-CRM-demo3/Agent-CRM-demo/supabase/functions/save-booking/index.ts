import { admin, checkSecret } from "../_shared/supa.ts";
import { buildBookingRow, mergeRetellCallPayload, patientAcct, recomputeReviewState } from "../_shared/booking.ts";
import { syncBookingToDomain } from "../_shared/sync-domain.ts";

const DEFAULT_DOCTOR = Deno.env.get("DEFAULT_DOCTOR") ?? "Dr. Adeel Rahman";

Deno.serve(async (req) => {
  if (!checkSecret(req)) return json({ error: "unauthorized" }, 401);

  let payload: any = {};
  try { payload = await req.json(); } catch (_) { /* ignore */ }

  const call = payload.call ?? {};
  const args = payload.args ?? payload;
  const callId: string = call.call_id ?? args.call_id ?? "";
  if (!callId) return json({ result: "saved" }, 200);

  if (!args.contact_number && call.from_number) args.contact_number = call.from_number;

  const db = admin();
  const row = buildBookingRow(args, { source: "voice" });
  row.call_id = callId;
  row.assigned_doctor = DEFAULT_DOCTOR;
  row.patient_acct = patientAcct(callId);
  if (call.start_timestamp) row.call_started_at = new Date(call.start_timestamp).toISOString();

  if (row.intake_method === "form" && (!row.insurance_status || row.insurance_status === "pending")) {
    row.insurance_status = "pending_form";
  }

  // Recompute review flags against the final merged row (upsert only overwrites the
  // columns present in `row`, so existing values fill the gaps).
  const { data: existing } = await db.from("bookings")
    .select("first_name, full_legal_name, reason, appointment_text, appointment_at, review_reasons, raw_payload")
    .eq("call_id", callId).maybeSingle();

  if (call && typeof call === "object" && !Array.isArray(call)) {
    row.raw_payload = mergeRetellCallPayload(existing?.raw_payload, call, callId);
  }
  const existingReasons: unknown[] = Array.isArray(existing?.review_reasons) ? existing.review_reasons : [];
  const rowReasons: unknown[] = Array.isArray(row.review_reasons) ? row.review_reasons : [];
  const review = recomputeReviewState({
    ...(existing ?? {}),
    ...row,
    review_reasons: [...existingReasons, ...rowReasons],
  });
  row.needs_review = review.needs_review;
  row.review_reasons = review.review_reasons;

  const { error } = await db.from("bookings").upsert(row, { onConflict: "call_id" });
  if (error) console.error("save-booking upsert error", error);

  await syncBookingToDomain(db, callId);

  return json({ result: "saved" }, 200);
});

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}