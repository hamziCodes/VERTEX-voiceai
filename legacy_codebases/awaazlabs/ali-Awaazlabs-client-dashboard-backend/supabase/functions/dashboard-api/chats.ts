import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import type { Identity, Result } from "./types.ts";
import { fail, ok } from "./types.ts";
import type { ChatRowDto, ChatsResponse } from "./types.ts";

interface DbSupportChatMessageRow {
  id: string;
  role: string;
  content: string;
  is_handoff_marker: boolean;
  created_at: string;
}

interface DbSupportChatSessionRow {
  id: string;
  location_id: string;
  channel: string;
  patient_label: string | null;
  purpose: string;
  outcome: string;
  language: string;
  message_count: number;
  started_at: string;
  last_message_at: string;
  location: { name: string | null } | null;
  support_chat_messages: DbSupportChatMessageRow[] | null;
}

const PURPOSE_LABELS: Record<string, string> = {
  general_support: "General support",
  appointment_cancel: "Appointment cancel",
  appointment_book: "Appointment booking",
  appointment_change: "Appointment change",
  missed_ai_call: "Missed AI call",
  link_access: "Link not opening",
  privacy_question: "Privacy question",
  technical_issue: "Technical issue",
  clinical_question: "Clinical question",
  human_follow_up: "Human follow-up",
};

function purposeLabel(slug: string): string {
  return PURPOSE_LABELS[slug] ?? slug.replace(/_/g, " ");
}

function mapSession(row: DbSupportChatSessionRow): ChatRowDto {
  const messages = (row.support_chat_messages ?? [])
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))
    .map((msg) => ({
      at: msg.created_at,
      speaker: msg.role === "patient" ? "patient" as const : "agent" as const,
      text: msg.content,
      isHandoffMarker: msg.is_handoff_marker,
    }));

  return {
    id: row.id,
    atUtc: row.started_at,
    channel: row.channel === "whatsapp" ? "whatsapp" : "web_chat",
    lastMessageAtUtc: row.last_message_at,
    outcome: row.outcome,
    messageCount: row.message_count,
    intent: purposeLabel(row.purpose),
    language: row.language === "es" ? "es" : row.language === "other" ? "other" : "en",
    locationId: row.location_id,
    locationName: row.location?.name ?? null,
    patientLabel: row.patient_label,
    messages,
  };
}

export async function listChats(
  db: SupabaseClient,
  identity: Identity,
  url: URL,
): Promise<Result<ChatsResponse>> {
  const limit = Math.min(Math.max(Number(url.searchParams.get("limit") ?? 100) || 100, 1), 200);
  const locationId = url.searchParams.get("location_id");

  let countBuilder = db
    .from("support_chat_sessions")
    .select("id", { count: "exact", head: true });
  if (locationId) {
    countBuilder = countBuilder.eq("location_id", locationId);
  }
  const { count, error: countError } = await countBuilder;

  if (countError !== null) {
    console.error("dashboard-api: chats count failed", countError);
    return fail(500, "internal_error", "Could not load chats");
  }

  if (identity.mode !== "PHI_BAA") {
    return ok({ kind: "aggregate", total: count ?? 0 });
  }

  let listQuery = db
    .from("support_chat_sessions")
    .select(
      "id,location_id,channel,patient_label,purpose,outcome,language,message_count,started_at,last_message_at," +
        "location:locations(name),support_chat_messages(id,role,content,is_handoff_marker,created_at)",
      { count: "exact" },
    )
    .order("last_message_at", { ascending: false })
    .limit(limit);

  if (locationId) {
    listQuery = listQuery.eq("location_id", locationId);
  }

  const { data, error } = await listQuery;
  if (error !== null) {
    console.error("dashboard-api: chats list failed", error);
    return fail(500, "internal_error", "Could not load chats");
  }

  return ok({
    rows: ((data ?? []) as DbSupportChatSessionRow[]).map(mapSession),
    total: count ?? data?.length ?? 0,
  });
}
