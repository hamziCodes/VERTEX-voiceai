// VOB queue list + workflow actions for the dashboard-api edge function.

import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { roleAtLeast } from "./auth.ts";
import type {
  CallTranscriptTurnDto,
  Identity,
  Result,
  VobCallMediaDto,
  VobListResponse,
  VobQueueRowDto,
  VobStatsDto,
  VobTimelineEntryDto,
} from "./types.ts";
import { fail, ok } from "./types.ts";
import { isUuid, maskPhone } from "./util.ts";

const VOB_TERMINAL_STATUSES = new Set([
  "verified",
  "partial_coverage",
  "needs_authorization",
  "needs_referral",
  "not_covered",
  "unable_to_verify",
  "member_not_found",
  "inactive_policy",
]);

const VOB_OVERVIEW_NEEDS_ATTENTION = new Set([
  "unable_to_verify",
  "member_not_found",
  "inactive_policy",
]);

const VOB_IN_PROGRESS_STATUSES = new Set(["dialing", "on_call", "pending_callback"]);

const DEFAULT_LOCATION_ID = "fd8bf778-6eb2-4da0-99ee-12280158fb75";

interface VobDashboardMeta {
  resolved?: boolean;
  resolvedReason?: string;
  staffNotes?: { at: string; body: string; author?: string }[];
  timeline?: VobTimelineEntryDto[];
}

interface DbVobRow {
  id: string;
  call_id: string;
  created_at: string;
  updated_at: string;
  queued_at: string;
  status: string;
  assigned_to: string | null;
  practice_name: string | null;
  patient_full_name: string | null;
  payer_name: string | null;
  plan_type: string | null;
  copay: string | null;
  individual_deductible_remaining: string | null;
  individual_deductible_total: string | null;
  individual_oop_remaining: string | null;
  individual_oop_total: string | null;
  cpt_coverage: string | null;
  cpt_limitations: string | null;
  prior_auth_required: string | null;
  referral_required: string | null;
  call_reference_number: string | null;
  call_summary: string | null;
  transcript: string | null;
  recording_url: string | null;
  raw_payload: Record<string, unknown> | null;
}

interface DbApptEmbed {
  id: string;
  vob_id: string | null;
  starts_at: string | null;
  location_id: string;
  location: { name: string } | null;
  patient: {
    first_name: string | null;
    last_name: string | null;
    full_legal_name: string | null;
    phone_e164: string | null;
  } | null;
}

interface DbBookingEmbed {
  call_id: string | null;
  contact_number: string | null;
  call_started_at: string | null;
  created_at: string;
  recording_url: string | null;
  transcript: string | null;
  call_summary: string | null;
}

function readDashboard(raw: Record<string, unknown> | null): VobDashboardMeta {
  if (raw === null) return {};
  const dash = raw.dashboard;
  if (typeof dash !== "object" || dash === null || Array.isArray(dash)) return {};
  return dash as VobDashboardMeta;
}

function mapDbStatusToUi(dbStatus: string): string {
  switch (dbStatus) {
    case "collecting":
      return "queued";
    case "in_progress":
      return "on_call";
    case "retry_needed":
      return "pending_callback";
    case "missing_information":
      return "member_not_found";
    case "failed_call":
      return "unable_to_verify";
    default:
      return dbStatus;
  }
}

function mapUiStatusToDb(uiStatus: string): string {
  switch (uiStatus) {
    case "queued":
      return "collecting";
    case "dialing":
    case "on_call":
      return "in_progress";
    case "pending_callback":
      return "retry_needed";
    case "member_not_found":
      return "missing_information";
    default:
      return uiStatus;
  }
}

function parseMoney(text: string | null): number | null {
  if (text === null || text.trim() === "") return null;
  const cleaned = text.replace(/[^0-9.]/g, "");
  const value = Number.parseFloat(cleaned);
  return Number.isFinite(value) ? value : null;
}

function parseBool(text: string | null): boolean {
  if (text === null || text.trim() === "") return false;
  const value = text.trim().toLowerCase();
  return ["yes", "true", "y", "required", "needed"].some((token) => value.includes(token));
}

function parseTranscript(transcript: string | null, fallbackAt: string): CallTranscriptTurnDto[] {
  if (!transcript) return [];
  return transcript
    .split(/\r?\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^(agent|assistant|ai|user|patient|caller|customer)\s*:\s*(.+)$/i);
      const role = (match?.[1] ?? "").toLowerCase();
      return {
        speaker: role === "agent" || role === "assistant" || role === "ai" ? "agent" as const : "patient" as const,
        at: fallbackAt,
        text: match?.[2]?.trim() || line,
      };
    });
}

function splitPatientName(fullName: string | null): { firstName: string | null; lastName: string | null } {
  const full = (fullName ?? "").trim();
  if (!full) return { firstName: null, lastName: null };
  const parts = full.split(/\s+/).filter(Boolean);
  return { firstName: parts[0] ?? null, lastName: parts.length > 1 ? parts.slice(1).join(" ") : null };
}

function isWorklistStatus(uiStatus: string, resolved: boolean): boolean {
  return uiStatus !== "verified" && !resolved;
}

async function resolveDefaultLocationId(db: SupabaseClient): Promise<string> {
  const { data } = await db.from("locations").select("id").order("created_at", { ascending: true }).limit(1).maybeSingle();
  const row = data as { id: string } | null;
  return row?.id ?? DEFAULT_LOCATION_ID;
}

async function loadLocationNames(db: SupabaseClient): Promise<Map<string, string>> {
  const { data, error } = await db.from("locations").select("id,name");
  if (error !== null) {
    console.error("dashboard-api: vob location name lookup failed", error);
    return new Map();
  }
  const names = new Map<string, string>();
  for (const row of (data ?? []) as { id: string; name: string }[]) {
    if (row.id && row.name) names.set(row.id, row.name);
  }
  return names;
}

function buildCoverageNotes(row: DbVobRow): string | null {
  const parts = [row.cpt_coverage, row.cpt_limitations].map((value) => (value ?? "").trim()).filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function buildTimeline(row: DbVobRow, dash: VobDashboardMeta): VobTimelineEntryDto[] {
  const base: VobTimelineEntryDto[] = [
    { at: row.queued_at ?? row.created_at, status: "queued", actor: "system" },
  ];
  if (row.updated_at !== row.created_at) {
    base.push({
      at: row.updated_at,
      status: mapDbStatusToUi(row.status),
      actor: "system",
      note: row.call_summary ?? undefined,
    });
  }
  const extra = dash.timeline ?? [];
  return [...base, ...extra].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
}

function mapVobRow(
  row: DbVobRow,
  appt: DbApptEmbed | undefined,
  booking: DbBookingEmbed | undefined,
  dash: VobDashboardMeta,
  defaultLocationId: string,
  locationNames: Map<string, string>,
): VobQueueRowDto {
  const uiStatus = mapDbStatusToUi(row.status);
  const resolved = dash.resolved === true;
  const locationId = appt?.location_id ?? defaultLocationId;
  const patientFromAppt = appt?.patient;
  const nameFromRow = splitPatientName(row.patient_full_name);
  const patientFirstName = patientFromAppt?.first_name ?? nameFromRow.firstName;
  const patientLastName = patientFromAppt?.last_name ?? nameFromRow.lastName;
  const phoneRaw = patientFromAppt?.phone_e164 ?? booking?.contact_number ?? null;
  const callAt = booking?.call_started_at ?? booking?.created_at ?? row.updated_at;
  const durationSeconds = booking?.call_started_at
    ? Math.max(0, Math.round((Date.parse(row.updated_at) - Date.parse(booking.call_started_at)) / 1000))
    : 0;
  const transcript = parseTranscript(row.transcript ?? booking?.transcript ?? null, callAt);
  const recordingUrl = row.recording_url ?? booking?.recording_url ?? null;
  const inProgress = ["queued", "dialing", "on_call", "pending_callback"].includes(uiStatus);

  const callMedia: VobCallMediaDto | null = row.call_id
    ? {
      callId: row.call_id,
      at: callAt,
      durationSeconds,
      recordingUrl,
      transcript: transcript.length > 0 ? transcript : null,
      summary: row.call_summary ?? booking?.call_summary ?? null,
      phoneMasked: maskPhone(phoneRaw),
      patientFirstName,
      patientLastName,
    }
    : null;

  return {
    id: row.id,
    callId: row.call_id,
    payer: row.payer_name?.trim() || "Unknown payer",
    plan: row.plan_type?.trim() || "—",
    status: uiStatus,
    appointmentId: appt?.id ?? null,
    appointmentStartsAt: appt?.starts_at ?? null,
    assignedTo: row.assigned_to,
    requestedAtUtc: row.queued_at ?? row.created_at,
    lastAttemptAtUtc: row.updated_at !== row.created_at ? row.updated_at : null,
    locationId,
    locationName: appt?.location?.name ?? locationNames.get(locationId) ?? null,
    patientFirstName,
    patientLastName,
    patientFullName: row.patient_full_name,
    phoneMasked: maskPhone(phoneRaw),
    priorAuthRequired: parseBool(row.prior_auth_required),
    referralRequired: parseBool(row.referral_required),
    ivrNavigationSucceeded: !inProgress && uiStatus !== "unable_to_verify",
    payerRepReached: !inProgress && !["queued", "dialing", "member_not_found", "unable_to_verify"].includes(uiStatus),
    resolved,
    resolvedReason: dash.resolvedReason ?? null,
    benefits: {
      copayUsd: parseMoney(row.copay),
      deductibleUsd: parseMoney(row.individual_deductible_remaining ?? row.individual_deductible_total),
      outOfPocketMaxUsd: parseMoney(row.individual_oop_remaining ?? row.individual_oop_total),
      coverageNotes: buildCoverageNotes(row),
    },
    attempts: row.call_id
      ? [{
        at: callAt,
        durationSeconds,
        outcome: row.call_summary?.trim() || uiStatus,
        interactionId: row.call_id,
        payerReferenceNumber: row.call_reference_number,
      }]
      : [],
    statusTimeline: buildTimeline(row, dash),
    staffNotes: (dash.staffNotes ?? []).map((note) => ({
      at: note.at,
      author: note.author ?? "staff",
      body: note.body,
    })),
    callMedia,
  };
}

/** Outbound payer-call pipeline: queued, on call, or awaiting callback. */
const VOB_PENDING_CALL_DB_STATUSES = ["collecting", "in_progress", "retry_needed"] as const;

function isVobTerminalUi(uiStatus: string): boolean {
  return VOB_TERMINAL_STATUSES.has(uiStatus);
}

function isVobOverviewNeedsAttentionUi(uiStatus: string): boolean {
  return VOB_OVERVIEW_NEEDS_ATTENTION.has(uiStatus);
}

function vobStatusGroupUi(uiStatus: string): keyof VobStatsDto["distributionByGroup"] {
  if (uiStatus === "verified") return "verified";
  if (isVobTerminalUi(uiStatus) && uiStatus !== "verified") return "needs_attention";
  return "pending";
}

function isSameUtcDay(iso: string, ref: Date): boolean {
  const d = new Date(iso);
  return (
    d.getUTCFullYear() === ref.getUTCFullYear() &&
    d.getUTCMonth() === ref.getUTCMonth() &&
    d.getUTCDate() === ref.getUTCDate()
  );
}

function isWithinTrailingDays(iso: string, days: number, now: Date): boolean {
  const age = (now.getTime() - Date.parse(iso)) / 86_400_000;
  return age >= 0 && age <= days;
}

export async function getVobStats(db: SupabaseClient, url: URL): Promise<Result<VobStatsDto>> {
  try {
    const locationId = (url.searchParams.get("location_id") ?? "").trim() || null;
    if (locationId !== null && !isUuid(locationId)) {
      return fail(400, "bad_request", "location_id must be a UUID");
    }

    const { data: vobRows, error } = await db
      .from("vob_queue")
      .select("id,status,created_at,updated_at,raw_payload")
      .order("created_at", { ascending: false })
      .limit(10000);
    if (error !== null) {
      console.error("dashboard-api: vob stats load failed", error);
      return fail(500, "internal_error", "Could not compute VOB stats");
    }

    const rows = (vobRows ?? []) as Pick<DbVobRow, "id" | "status" | "created_at" | "updated_at" | "raw_payload">[];
    const vobIds = rows.map((row) => row.id);

    const apptLoc = new Map<string, string>();
    if (vobIds.length > 0) {
      const { data: appts, error: apptError } = await db
        .from("appointments")
        .select("vob_id,location_id")
        .in("vob_id", vobIds);
      if (apptError !== null) {
        console.error("dashboard-api: vob stats location lookup failed", apptError);
        return fail(500, "internal_error", "Could not compute VOB stats");
      }
      for (const appt of (appts ?? []) as { vob_id: string | null; location_id: string }[]) {
        if (appt.vob_id) apptLoc.set(appt.vob_id, appt.location_id);
      }
    }

    const defaultLocationId = await resolveDefaultLocationId(db);
    const now = new Date();

    const stats: VobStatsDto = {
      inProgress: 0,
      inProgressBySubStatus: { queued: 0, dialing: 0, on_call: 0, pending_callback: 0 },
      completedToday: 0,
      completedThisWeek: 0,
      verifiedRateThisWeek: null,
      overviewNeedsAttention: 0,
      worklistNeedsAttention: 0,
      distributionByGroup: { verified: 0, pending: 0, needs_attention: 0 },
    };

    let terminalThisWeek = 0;
    let verifiedThisWeek = 0;

    for (const row of rows) {
      const locId = apptLoc.get(row.id) ?? defaultLocationId;
      if (locationId !== null && locId !== locationId) continue;

      const uiStatus = mapDbStatusToUi(row.status);
      const dash = readDashboard(row.raw_payload);
      const resolved = dash.resolved === true;
      const lastAttemptAt = row.updated_at !== row.created_at ? row.updated_at : null;

      if (!resolved) {
        const group = vobStatusGroupUi(uiStatus);
        stats.distributionByGroup[group] += 1;
      }

      if (!resolved && (uiStatus === "queued" || VOB_IN_PROGRESS_STATUSES.has(uiStatus))) {
        stats.inProgress += 1;
      }
      if (!resolved && uiStatus === "queued") stats.inProgressBySubStatus.queued += 1;
      if (!resolved && uiStatus === "dialing") stats.inProgressBySubStatus.dialing += 1;
      if (!resolved && uiStatus === "on_call") stats.inProgressBySubStatus.on_call += 1;
      if (!resolved && uiStatus === "pending_callback") stats.inProgressBySubStatus.pending_callback += 1;

      if (!resolved && isVobOverviewNeedsAttentionUi(uiStatus)) stats.overviewNeedsAttention += 1;
      if (!resolved && isVobTerminalUi(uiStatus) && uiStatus !== "verified") stats.worklistNeedsAttention += 1;

      if (isVobTerminalUi(uiStatus) && lastAttemptAt !== null) {
        if (isSameUtcDay(lastAttemptAt, now)) stats.completedToday += 1;
        if (isWithinTrailingDays(lastAttemptAt, 7, now)) {
          terminalThisWeek += 1;
          if (uiStatus === "verified") verifiedThisWeek += 1;
        }
      }
    }

    stats.completedThisWeek = terminalThisWeek;
    stats.verifiedRateThisWeek = terminalThisWeek === 0 ? null : verifiedThisWeek / terminalThisWeek;

    return ok(stats);
  } catch (e) {
    console.error("dashboard-api: vob stats failed", e);
    return fail(500, "internal_error", "Could not compute VOB stats");
  }
}

export async function countVobPendingInsuranceCalls(
  db: SupabaseClient,
  locationId: string | null,
): Promise<number> {
  const { data: vobRows, error } = await db
    .from("vob_queue")
    .select("id,status,raw_payload")
    .in("status", [...VOB_PENDING_CALL_DB_STATUSES]);
  if (error !== null) {
    console.error("dashboard-api: vob pending call count failed", error);
    return 0;
  }

  const rows = (vobRows ?? []) as Pick<DbVobRow, "id" | "status" | "raw_payload">[];
  if (rows.length === 0) return 0;

  const unresolved = rows.filter((row) => readDashboard(row.raw_payload).resolved !== true);
  if (locationId === null) return unresolved.length;

  const vobIds = unresolved.map((row) => row.id);
  const { data: appts, error: apptError } = await db
    .from("appointments")
    .select("vob_id,location_id")
    .in("vob_id", vobIds);
  if (apptError !== null) {
    console.error("dashboard-api: vob pending call location lookup failed", apptError);
    return unresolved.length;
  }

  const defaultLocationId = await resolveDefaultLocationId(db);
  const apptLoc = new Map<string, string>();
  for (const appt of (appts ?? []) as { vob_id: string | null; location_id: string }[]) {
    if (appt.vob_id) apptLoc.set(appt.vob_id, appt.location_id);
  }

  let count = 0;
  for (const row of unresolved) {
    const locId = apptLoc.get(row.id) ?? defaultLocationId;
    if (locId === locationId) count += 1;
  }
  return count;
}

export async function listVobQueue(
  db: SupabaseClient,
  identity: Identity,
  url: URL,
): Promise<Result<VobListResponse>> {
  const locationId = (url.searchParams.get("location_id") ?? "").trim() || null;
  const limit = Math.min(Math.max(Number(url.searchParams.get("limit") ?? 500) || 500, 1), 1000);

  const { data: vobRows, error } = await db
    .from("vob_queue")
    .select("*")
    .order("priority_position", { ascending: true, nullsFirst: false })
    .order("created_at", { ascending: false })
    .limit(limit);
  if (error !== null) {
    console.error("dashboard-api: vob_queue list failed", error);
    return fail(500, "internal_error", "Could not load VOB queue");
  }

  const rows = (vobRows ?? []) as DbVobRow[];
  const vobIds = rows.map((row) => row.id);
  const callIds = rows.map((row) => row.call_id).filter(Boolean);

  const apptByVobId = new Map<string, DbApptEmbed>();
  if (vobIds.length > 0) {
    const { data: appts, error: apptError } = await db
      .from("appointments")
      .select(
        "id,vob_id,starts_at,location_id,location:locations(name),patient:patients(first_name,last_name,full_legal_name,phone_e164)",
      )
      .in("vob_id", vobIds);
    if (apptError !== null) {
      console.error("dashboard-api: vob appointment lookup failed", apptError);
      return fail(500, "internal_error", "Could not load VOB queue");
    }
    for (const appt of (appts ?? []) as DbApptEmbed[]) {
      if (appt.vob_id) apptByVobId.set(appt.vob_id, appt);
    }
  }

  const bookingByCallId = new Map<string, DbBookingEmbed>();
  if (callIds.length > 0) {
    const { data: bookings, error: bookingError } = await db
      .from("bookings")
      .select("call_id,contact_number,call_started_at,created_at,recording_url,transcript,call_summary")
      .in("call_id", callIds);
    if (bookingError !== null) {
      console.error("dashboard-api: vob booking lookup failed", bookingError);
      return fail(500, "internal_error", "Could not load VOB queue");
    }
    for (const booking of (bookings ?? []) as DbBookingEmbed[]) {
      if (booking.call_id) bookingByCallId.set(booking.call_id, booking);
    }
  }

  const defaultLocationId = await resolveDefaultLocationId(db);
  const locationNames = await loadLocationNames(db);

  if (identity.mode !== "PHI_BAA") {
    let total = 0;
    for (const row of rows) {
      const dash = readDashboard(row.raw_payload);
      const uiStatus = mapDbStatusToUi(row.status);
      const appt = apptByVobId.get(row.id);
      const locId = appt?.location_id ?? defaultLocationId;
      if (locationId !== null && locId !== locationId) continue;
      if (isWorklistStatus(uiStatus, dash.resolved === true)) total += 1;
    }
    return ok({ kind: "aggregate", total });
  }

  const mapped: VobQueueRowDto[] = [];
  for (const row of rows) {
    const dash = readDashboard(row.raw_payload);
    const appt = apptByVobId.get(row.id);
    const locId = appt?.location_id ?? defaultLocationId;
    if (locationId !== null && locId !== locationId) continue;
    mapped.push(mapVobRow(row, appt, bookingByCallId.get(row.call_id), dash, defaultLocationId, locationNames));
  }

  return ok({ rows: mapped, total: mapped.length });
}

async function writeAudit(
  db: SupabaseClient,
  event: { actor: string; action: string; entity: string; entityId: string | null; metadata: Record<string, unknown> | null },
): Promise<boolean> {
  const { error } = await db.from("audit_events").insert({
    actor: event.actor,
    action: event.action,
    entity: event.entity,
    entity_id: event.entityId,
    metadata: event.metadata,
  });
  if (error !== null) {
    console.error("dashboard-api: audit_events insert failed", error);
    return false;
  }
  return true;
}

async function loadVobRow(db: SupabaseClient, vobId: string): Promise<DbVobRow | null> {
  const { data, error } = await db.from("vob_queue").select("*").eq("id", vobId).maybeSingle();
  if (error !== null) {
    console.error("dashboard-api: vob lookup failed", error);
    return null;
  }
  return data as DbVobRow | null;
}

async function persistDashboard(
  db: SupabaseClient,
  row: DbVobRow,
  patch: (dash: VobDashboardMeta) => VobDashboardMeta,
  dbPatch: Record<string, unknown> = {},
): Promise<boolean> {
  const raw = row.raw_payload ?? {};
  const dash = readDashboard(raw);
  const nextRaw = { ...raw, dashboard: patch(dash) };
  const { error } = await db.from("vob_queue").update({ ...dbPatch, raw_payload: nextRaw }).eq("id", row.id);
  if (error !== null) {
    console.error("dashboard-api: vob update failed", error);
    return false;
  }
  return true;
}

function appendTimeline(dash: VobDashboardMeta, entry: VobTimelineEntryDto): VobDashboardMeta {
  return { ...dash, timeline: [...(dash.timeline ?? []), entry] };
}

export async function handleVobAction(
  db: SupabaseClient,
  identity: Identity,
  action: string,
  record: Record<string, unknown>,
): Promise<Result<unknown>> {
  if (!roleAtLeast(identity.role, "STAFF")) {
    return fail(403, "forbidden", "VOB queue actions require STAFF role or above");
  }

  const vobId = typeof record.vobId === "string" && isUuid(record.vobId) ? record.vobId : null;
  if (vobId === null) return fail(400, "bad_request", "vobId must be a UUID");

  const row = await loadVobRow(db, vobId);
  if (row === null) return fail(404, "not_found", "VOB record not found");

  const dash = readDashboard(row.raw_payload);
  const uiStatus = mapDbStatusToUi(row.status);
  const now = new Date().toISOString();

  switch (action) {
    case "vob_retry": {
      const timelineEntry: VobTimelineEntryDto = {
        at: now,
        status: "queued",
        actor: identity.actor,
        note: "Re-queued for verification",
      };
      const saved = await persistDashboard(
        db,
        row,
        (current) => appendTimeline({ ...current, resolved: false }, timelineEntry),
        { status: "collecting", assigned_to: row.assigned_to },
      );
      if (!saved) return fail(500, "internal_error", "Could not retry VOB verification");
      const audited = await writeAudit(db, {
        actor: identity.actor,
        action: "vob_retry",
        entity: "vob_queue",
        entityId: vobId,
        metadata: null,
      });
      if (!audited) return fail(500, "logging_failed", "VOB was re-queued but audit logging failed");
      return ok({ id: vobId, status: "queued" });
    }
    case "vob_resolve": {
      const reason = typeof record.reason === "string" ? record.reason.trim() : "";
      if (!reason) return fail(400, "bad_request", "reason is required");
      const timelineEntry: VobTimelineEntryDto = {
        at: now,
        status: uiStatus,
        actor: identity.actor,
        note: `Resolved: ${reason}`,
      };
      const saved = await persistDashboard(
        db,
        row,
        (current) => appendTimeline({ ...current, resolved: true, resolvedReason: reason }, timelineEntry),
      );
      if (!saved) return fail(500, "internal_error", "Could not resolve VOB verification");
      const audited = await writeAudit(db, {
        actor: identity.actor,
        action: "vob_resolve",
        entity: "vob_queue",
        entityId: vobId,
        metadata: { reason },
      });
      if (!audited) return fail(500, "logging_failed", "VOB was resolved but audit logging failed");
      return ok({ id: vobId, resolved: true, reason });
    }
    case "vob_escalate": {
      const assignee = typeof record.assignee === "string" ? record.assignee.trim() : "";
      if (!assignee) return fail(400, "bad_request", "assignee is required");
      const timelineEntry: VobTimelineEntryDto = {
        at: now,
        status: uiStatus,
        actor: identity.actor,
        note: `Escalated to ${assignee}`,
      };
      const saved = await persistDashboard(
        db,
        row,
        (current) => appendTimeline(current, timelineEntry),
        { assigned_to: assignee },
      );
      if (!saved) return fail(500, "internal_error", "Could not escalate VOB verification");
      const audited = await writeAudit(db, {
        actor: identity.actor,
        action: "vob_escalate",
        entity: "vob_queue",
        entityId: vobId,
        metadata: { assignee },
      });
      if (!audited) return fail(500, "logging_failed", "VOB was escalated but audit logging failed");
      return ok({ id: vobId, assignedTo: assignee });
    }
    case "vob_add_note": {
      const body = typeof record.body === "string" ? record.body.trim() : "";
      if (body.length < 1 || body.length > 4000) {
        return fail(400, "bad_request", "body must be a string of 1 to 4000 characters");
      }
      const note = { at: now, author: identity.actor, body };
      const timelineEntry: VobTimelineEntryDto = {
        at: now,
        status: uiStatus,
        actor: identity.actor,
        note: "Note added",
      };
      const saved = await persistDashboard(
        db,
        row,
        (current) => appendTimeline({
          ...current,
          staffNotes: [...(current.staffNotes ?? []), note],
        }, timelineEntry),
      );
      if (!saved) return fail(500, "internal_error", "Could not add VOB note");
      const audited = await writeAudit(db, {
        actor: identity.actor,
        action: "vob_add_note",
        entity: "vob_queue",
        entityId: vobId,
        metadata: { body_length: body.length },
      });
      if (!audited) return fail(500, "logging_failed", "VOB note was saved but audit logging failed");
      return ok({ id: vobId, note });
    }
    default:
      return fail(400, "unknown_action", "Unknown VOB action");
  }
}
