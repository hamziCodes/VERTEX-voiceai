import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

import { patientAcct } from "./booking.ts";

const DEFAULT_DOCTOR = Deno.env.get("DEFAULT_DOCTOR") ?? "Dr. Adeel Rahman";

type RetellPayload = {
  call?: Record<string, unknown>;
  data?: Record<string, unknown>;
  transcript?: unknown;
  transcript_with_tool_calls?: unknown;
  transcript_object?: unknown;
};

/** Pull the latest transcript text from a Retell webhook payload. */
export function extractTranscriptFromRetellPayload(payload: RetellPayload): string {
  const data = payload.data && typeof payload.data === "object" ? payload.data : {};
  const dataCall = data.call && typeof data.call === "object" ? data.call as Record<string, unknown> : {};
  const call = payload.call && typeof payload.call === "object" ? payload.call : {};

  const candidates = [
    call.transcript,
    call.transcript_with_tool_calls,
    payload.transcript,
    payload.transcript_with_tool_calls,
    call.transcript_object,
    payload.transcript_object,
    dataCall.transcript,
    dataCall.transcript_with_tool_calls,
    dataCall.transcript_object,
    data.transcript,
    data.transcript_with_tool_calls,
    data.transcript_object,
  ];

  for (const candidate of candidates) {
    const transcript = stringifyTranscript(candidate);
    if (transcript) return transcript;
  }
  return "";
}

function stringifyTranscript(value: unknown): string {
  if (!value) return "";
  if (typeof value === "string") return value.trim();
  if (Array.isArray(value)) {
    return value
      .map((turn) => stringifyTranscriptTurn(turn))
      .filter(Boolean)
      .join("\n")
      .trim();
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value).trim();
}

function stringifyTranscriptTurn(turn: unknown): string {
  if (!turn || typeof turn !== "object") return stringifyTranscript(turn);
  const record = turn as Record<string, unknown>;
  const role = stringValue(record.role ?? record.speaker ?? record.user ?? record.source);
  const content = stringValue(record.content ?? record.text ?? record.words ?? record.transcript);
  if (!content) return "";
  return role ? `${role}: ${content}` : content;
}

function stringValue(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map(stringValue).filter(Boolean).join(" ").trim();
  return String(value).trim();
}

function timestampValue(value: unknown): string | null {
  if (typeof value !== "number") return null;
  const ms = value > 10_000_000_000 ? value : value * 1000;
  return new Date(ms).toISOString();
}

/**
 * Write transcript text immediately so the dashboard can show live turns before Groq finishes.
 * Does not run field extraction or merge CRM columns.
 */
export async function persistLiveBookingTranscript(
  db: SupabaseClient,
  callId: string,
  transcript: string,
  call: Record<string, unknown> = {},
): Promise<void> {
  const text = transcript.trim();
  if (!text) return;

  const { data: existing, error: fetchError } = await db.from("bookings")
    .select("raw_payload, transcript")
    .eq("call_id", callId)
    .maybeSingle();
  if (fetchError) throw fetchError;

  const existingRaw = existing?.raw_payload && typeof existing.raw_payload === "object" && !Array.isArray(existing.raw_payload)
    ? existing.raw_payload as Record<string, unknown>
    : {};
  const existingCall = existingRaw.call && typeof existingRaw.call === "object" && !Array.isArray(existingRaw.call)
    ? existingRaw.call as Record<string, unknown>
    : {};

  const mergedCall = { ...existingCall, ...call, call_id: callId };
  const patch: Record<string, unknown> = {
    transcript: text,
    raw_payload: {
      ...existingRaw,
      call: mergedCall,
    },
  };

  const startedAt = timestampValue(mergedCall.start_timestamp);
  if (startedAt) patch.call_started_at = startedAt;
  const agentName = stringValue(mergedCall.agent_name);
  if (agentName) patch.representative = agentName;
  const fromNumber = stringValue(mergedCall.from_number);
  if (fromNumber) patch.contact_number = fromNumber;

  if (existing) {
    const { error } = await db.from("bookings").update(patch).eq("call_id", callId);
    if (error) throw error;
    return;
  }

  const { error } = await db.from("bookings").insert({
    ...patch,
    call_id: callId,
    call_started_at: startedAt ?? new Date().toISOString(),
    assigned_doctor: DEFAULT_DOCTOR,
    patient_acct: patientAcct(callId),
    source: "retell_live_transcript",
  });
  if (error) throw error;
}

export async function persistLiveVobTranscript(
  db: SupabaseClient,
  callId: string,
  transcript: string,
): Promise<void> {
  const text = transcript.trim();
  if (!text) return;

  const { data: existing, error: fetchError } = await db.from("vob_queue")
    .select("id, transcript")
    .eq("call_id", callId)
    .maybeSingle();
  if (fetchError) throw fetchError;

  if (existing) {
    const { error } = await db.from("vob_queue").update({ transcript: text }).eq("call_id", callId);
    if (error) throw error;
    return;
  }

  const { error } = await db.from("vob_queue").insert({
    call_id: callId,
    status: "collecting",
    transcript: text,
  });
  if (error) throw error;
}
