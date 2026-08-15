// dashboard-api — backend for the AwaazLabs client dashboard Appointments and Escalations tabs.
//
// Called only by the Next.js server proxy (Clerk-authenticated there), which
// forwards a shared secret plus trusted identity headers. See CONTRACT.md for
// the full endpoint contract this function serves.
//
// Routing:
//   GET  ?resource=appointments   list + filters (PHI rows or aggregate count)
//   GET  ?resource=stats          dashboard stat tiles
//   GET  ?resource=appointment&id single appointment full detail
//   GET  ?resource=calls          Retell calls + transcript rows
//   GET  ?resource=chats          patient support web chat sessions
//   GET  ?resource=escalations    list + filters (PHI rows or aggregate count)
//   GET  ?resource=escalation&id  single escalation detail
//   GET  ?resource=escalation_stats escalation stat tiles
//   GET  ?resource=recording&call_id=  upstream recording URL for server-side proxy
//   GET  ?resource=notifications   top-bar bell counts (escalations + VOB pending calls)
//   GET  ?resource=vob_stats        overview VOB stat tiles + distribution (no PHI)
//   POST { action: ... }          appointment + escalation + vob actions

import { admin } from "../_shared/supa.ts";
import { authenticate, corsHeaders } from "./auth.ts";
import { handleAction } from "./actions.ts";
import {
  getAppointmentDetail,
  getCallRecording,
  getEscalationDetail,
  getEscalationStats,
  getStats,
  listAppointments,
  listCalls,
  listEscalations,
} from "./queries.ts";
import { listChats } from "./chats.ts";
import { getVobStats, listVobQueue } from "./vob-queue.ts";
import { getNotificationCounts } from "./notifications.ts";
import { getDashboardRuntimeSettings } from "./runtime-settings.ts";
import type { Result } from "./types.ts";
import { fail } from "./types.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const auth = authenticate(req);
    if (!auth.ok) return toResponse(auth);
    const identity = auth.data;
    const db = admin();

    if (req.method === "GET") {
      const url = new URL(req.url);
      const resource = url.searchParams.get("resource") ?? "";
      let result: Result<unknown>;
      switch (resource) {
        case "appointments":
          result = await listAppointments(db, identity, url);
          break;
        case "stats":
          result = await getStats(db, url);
          break;
        case "appointment":
          result = await getAppointmentDetail(db, identity, url.searchParams.get("id") ?? "");
          break;
        case "calls":
          result = await listCalls(db, identity, url);
          break;
        case "chats":
          result = await listChats(db, identity, url);
          break;
        case "escalations":
          result = await listEscalations(db, identity, url);
          break;
        case "escalation":
          result = await getEscalationDetail(db, identity, url.searchParams.get("id") ?? "");
          break;
        case "escalation_stats":
          result = await getEscalationStats(db);
          break;
        case "recording":
          result = await getCallRecording(db, identity, url.searchParams.get("call_id") ?? "");
          break;
        case "vob_queue":
          result = await listVobQueue(db, identity, url);
          break;
        case "vob_stats":
          result = await getVobStats(db, url);
          break;
        case "notifications":
          result = await getNotificationCounts(db, identity, url);
          break;
        case "runtime_settings":
          result = await getDashboardRuntimeSettings(db);
          break;
        default:
          result = fail(400, "unknown_resource", "resource must be one of: appointments, stats, appointment, calls, chats, escalations, escalation, escalation_stats, recording, vob_queue, vob_stats, notifications, runtime_settings");
      }
      return toResponse(result);
    }

    if (req.method === "POST") {
      let body: unknown;
      try {
        body = await req.json();
      } catch (_) {
        return toResponse(fail(400, "bad_json", "Request body must be valid JSON"));
      }
      return toResponse(await handleAction(db, identity, body));
    }

    return toResponse(fail(405, "method_not_allowed", "Only GET, POST and OPTIONS are supported"));
  } catch (e) {
    // Last-resort catch: never leak internals to the caller.
    console.error("dashboard-api: unhandled error", e);
    return toResponse(fail(500, "internal_error", "Unexpected server error"));
  }
});

function toResponse(result: Result<unknown>): Response {
  const status = result.ok ? 200 : result.status;
  const payload = result.ok
    ? { data: result.data }
    : { error: { code: result.code, message: result.message } };
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders },
  });
}
