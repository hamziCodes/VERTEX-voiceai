// Notification counts for the top-bar bell (aggregate only — no PHI).

import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import type { Identity, NotificationCountsDto, Result } from "./types.ts";
import { fail, ok } from "./types.ts";
import { countVobPendingInsuranceCalls } from "./vob-queue.ts";

export async function getNotificationCounts(
  db: SupabaseClient,
  _identity: Identity,
  url: URL,
): Promise<Result<NotificationCountsDto>> {
  const locationId = (url.searchParams.get("location_id") ?? "").trim() || null;

  try {
    let escQuery = db
      .from("escalations")
      .select("id", { count: "exact", head: true })
      .neq("status", "resolved");
    if (locationId !== null) escQuery = escQuery.eq("location_id", locationId);

    const [escResult, vobPendingCalls] = await Promise.all([
      escQuery,
      countVobPendingInsuranceCalls(db, locationId),
    ]);

    if (escResult.error !== null) {
      console.error("dashboard-api: notification escalation count failed", escResult.error);
      return fail(500, "internal_error", "Could not load notification counts");
    }

    const escalationsPending = escResult.count ?? 0;
    const total = escalationsPending + vobPendingCalls;

    return ok({
      total,
      escalationsPending,
      vobPendingCalls,
    });
  } catch (e) {
    console.error("dashboard-api: notification counts failed", e);
    return fail(500, "internal_error", "Could not load notification counts");
  }
}
