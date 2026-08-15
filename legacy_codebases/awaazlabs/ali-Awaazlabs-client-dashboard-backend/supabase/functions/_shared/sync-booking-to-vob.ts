// sync-booking-to-vob.ts — auto-push bookings → vob_queue when all intake fields are filled.
//
// Required on bookings (all non-null):
//   patient name, patient dob, payer_name, member_id,
//   and date_of_service OR preferred appointment time.
//
// Bookings is never deleted; this upserts vob_queue on call_id.

import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { str } from "./validate.ts";

const FINAL_VOB_STATUSES = new Set([
  "verified",
  "partial_coverage",
  "needs_authorization",
  "needs_referral",
  "not_covered",
  "inactive_policy",
  "unable_to_verify",
  "retry_needed",
  "failed_call",
]);

type SyncContext = {
  booking: Record<string, unknown>;
  appointment: Record<string, unknown> | null;
};

/**
 * Sync a bookings row into vob_queue only when every required intake field is present.
 */
export async function syncBookingToVobQueue(db: SupabaseClient, callId: string): Promise<void> {
  try {
    await sync(db, callId);
  } catch (e) {
    console.error("sync-booking-to-vob: error syncing", callId, e instanceof Error ? e.message : String(e));
  }
}

export interface BackfillBookingsToVobResult {
  scanned: number;
  ready: number;
  pushed: number;
  skippedNoCallId: number;
  notReady: number;
}

/** Process every existing bookings row and push eligible ones to vob_queue. */
export async function backfillAllBookingsToVob(db: SupabaseClient): Promise<BackfillBookingsToVobResult> {
  const result: BackfillBookingsToVobResult = {
    scanned: 0,
    ready: 0,
    pushed: 0,
    skippedNoCallId: 0,
    notReady: 0,
  };

  const pageSize = 200;
  let offset = 0;

  while (true) {
    const { data, error } = await db
      .from("bookings")
      .select("*")
      .order("created_at", { ascending: true })
      .range(offset, offset + pageSize - 1);
    if (error) throw error;
    if (!data?.length) break;

    for (const booking of data) {
      result.scanned += 1;
      const callId = typeof booking.call_id === "string" ? booking.call_id.trim() : "";
      if (!callId) {
        result.skippedNoCallId += 1;
        continue;
      }

      const { data: appointment } = await db
        .from("appointments")
        .select("id, starts_at, booking_id, call_id")
        .eq("call_id", callId)
        .order("starts_at", { ascending: false, nullsFirst: false })
        .limit(1)
        .maybeSingle();

      const ctx: SyncContext = {
        booking: booking as Record<string, unknown>,
        appointment: appointment as Record<string, unknown> | null,
      };

      if (!isBookingReadyForVob(ctx)) {
        result.notReady += 1;
        continue;
      }

      result.ready += 1;
      const hadVob = await db.from("vob_queue").select("id").eq("call_id", callId).maybeSingle();
      await sync(db, callId);
      const hasVob = await db.from("vob_queue").select("id, queue_ready").eq("call_id", callId).maybeSingle();
      if (hasVob.data?.queue_ready) {
        if (!hadVob.data) result.pushed += 1;
        else result.pushed += 1;
      }
    }

    offset += data.length;
    if (data.length < pageSize) break;
  }

  return result;
}

async function sync(db: SupabaseClient, callId: string): Promise<void> {
  const { data: booking, error: bookingError } = await db.from("bookings").select("*").eq("call_id", callId).maybeSingle();
  if (bookingError || !booking) return;

  const { data: appointment } = await db
    .from("appointments")
    .select("id, starts_at, booking_id, call_id")
    .eq("call_id", callId)
    .order("starts_at", { ascending: false, nullsFirst: false })
    .limit(1)
    .maybeSingle();

  const ctx: SyncContext = {
    booking: booking as Record<string, unknown>,
    appointment: appointment as Record<string, unknown> | null,
  };

  if (!isBookingReadyForVob(ctx)) {
    return;
  }

  const { data: existing, error: vobError } = await db.from("vob_queue").select("*").eq("call_id", callId).maybeSingle();
  if (vobError) throw vobError;

  const patch = buildPatchFromBooking(ctx, existing as Record<string, unknown> | null);
  const now = new Date().toISOString();
  const wasReady = existing?.queue_ready === true;

  const row: Record<string, unknown> = {
    ...patch,
    call_id: callId,
    queue_ready: true,
    missing_required_fields: [],
    ready_at: wasReady ? existing?.ready_at ?? now : now,
    last_extracted_at: now,
    raw_payload: buildRawPayload(existing?.raw_payload, ctx),
  };

  const currentStatus = String(existing?.status ?? "");
  if (!FINAL_VOB_STATUSES.has(currentStatus)) {
    row.status = "collecting";
  }

  if (!existing) {
    row.queued_at = now;
    row.priority_position = await nextPriorityPosition(db);
  } else if (!wasReady && !hasValue(existing.priority_position)) {
    row.priority_position = await nextPriorityPosition(db);
  }

  const { data: upserted, error: upsertError } = await db
    .from("vob_queue")
    .upsert(row, { onConflict: "call_id" })
    .select("id")
    .single();
  if (upsertError) throw upsertError;

  if (upserted?.id) {
    await db
      .from("appointments")
      .update({ vob_id: upserted.id })
      .eq("call_id", callId)
      .is("vob_id", null);
  }
}

/** All required bookings fields must be non-null before pushing to vob_queue. */
export function isBookingReadyForVob(ctx: SyncContext): boolean {
  const { booking, appointment } = ctx;
  if (!hasValue(resolvePatientName(booking))) return false;
  if (!hasValue(booking.dob)) return false;
  if (!hasValue(booking.payer_name)) return false;
  if (!hasValue(booking.member_id)) return false;
  if (!hasValue(booking.date_of_service) && !hasPreferredAppointmentTime(booking, appointment)) return false;
  return true;
}

function buildPatchFromBooking(
  ctx: SyncContext,
  existing: Record<string, unknown> | null,
): Record<string, unknown> {
  const patch: Record<string, unknown> = {
    patient_full_name: resolvePatientName(ctx.booking),
    patient_dob: ctx.booking.dob,
    payer_name: ctx.booking.payer_name,
    member_id: ctx.booking.member_id,
    date_of_service: resolveDateOfService(ctx),
    plan_type: ctx.booking.plan_type ?? null,
    practice_name: ctx.booking.practice ?? null,
    provider_name: ctx.booking.provider_name ?? null,
    provider_npi: ctx.booking.npi ?? null,
    tax_id: ctx.booking.tax_id ?? null,
    cpt_codes: ctx.booking.cpt_codes ?? null,
    service_type: ctx.booking.reason ?? null,
    transcript: ctx.booking.transcript ?? null,
    call_summary: ctx.booking.call_summary ?? null,
    recording_url: ctx.booking.recording_url ?? null,
  };

  if (!existing || !FINAL_VOB_STATUSES.has(String(existing.status ?? ""))) {
    // insurance_status is stored in raw_payload; vob_queue.status is workflow-only.
  }

  const result: Record<string, unknown> = {};
  for (const [field, value] of Object.entries(patch)) {
    if (!hasValue(value)) continue;
    const current = existing?.[field];
    if (!hasValue(current) || field === "status" && !FINAL_VOB_STATUSES.has(String(current))) {
      result[field] = value;
    }
  }
  return result;
}

function hasPreferredAppointmentTime(
  booking: Record<string, unknown>,
  appointment: Record<string, unknown> | null,
): boolean {
  return (
    hasValue(appointment?.starts_at) ||
    hasValue(booking.appointment_at) ||
    hasValue(booking.appointment_text)
  );
}

function resolvePatientName(booking: Record<string, unknown>): string | null {
  return str(booking.full_legal_name) ?? str(booking.first_name);
}

function resolveAppointmentStartsAt(ctx: SyncContext): string | null {
  const startsAt = ctx.appointment?.starts_at;
  if (hasValue(startsAt)) return String(startsAt);
  const bookingAt = ctx.booking.appointment_at;
  if (hasValue(bookingAt)) return String(bookingAt);
  return null;
}

function resolveDateOfService(ctx: SyncContext): string | null {
  const dos = ctx.booking.date_of_service;
  if (hasValue(dos)) return String(dos).slice(0, 10);

  const startsAt = resolveAppointmentStartsAt(ctx);
  if (hasValue(startsAt)) {
    const d = new Date(startsAt);
    if (!Number.isNaN(d.getTime())) return d.toISOString().slice(0, 10);
  }
  return null;
}

function hasValue(value: unknown): boolean {
  return value !== null && value !== undefined && String(value).trim() !== "";
}

async function nextPriorityPosition(db: SupabaseClient): Promise<number> {
  const { data, error } = await db
    .from("vob_queue")
    .select("priority_position")
    .not("priority_position", "is", null)
    .order("priority_position", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) throw error;
  const current = typeof data?.priority_position === "number" ? data.priority_position : 0;
  return current + 1;
}

function buildRawPayload(
  existingRaw: unknown,
  ctx: SyncContext,
): Record<string, unknown> {
  const base = existingRaw && typeof existingRaw === "object" && !Array.isArray(existingRaw)
    ? existingRaw as Record<string, unknown>
    : {};

  return {
    ...base,
    booking_vob_sync: {
      synced_at: new Date().toISOString(),
      booking_id: ctx.booking.id ?? null,
      appointment_id: ctx.appointment?.id ?? null,
      appointment_starts_at: resolveAppointmentStartsAt(ctx),
      form_status: ctx.booking.form_status ?? null,
      intake_method: ctx.booking.intake_method ?? null,
      insurance_status: ctx.booking.insurance_status ?? null,
      plan_type: ctx.booking.plan_type ?? null,
      queue_ready: true,
      missing_required_fields: [],
      source: "bookings",
    },
  };
}
