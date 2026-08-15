import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getRuntimeSettings, setGroqTableFillEnabled } from "../_shared/extraction-settings.ts";
import type { Identity, Result } from "./types.ts";
import { fail, ok } from "./types.ts";
import { roleAtLeast } from "./auth.ts";

export async function getDashboardRuntimeSettings(
  db: SupabaseClient,
): Promise<Result<{ useGroqTableFill: boolean }>> {
  return ok(await getRuntimeSettings(db));
}

export async function setDashboardRuntimeSettings(
  db: SupabaseClient,
  identity: Identity,
  body: Record<string, unknown>,
): Promise<Result<{ useGroqTableFill: boolean }>> {
  if (!roleAtLeast(identity.role, "OWNER")) {
    return fail(403, "forbidden", "Only owners may change extraction settings");
  }
  if (typeof body.useGroqTableFill !== "boolean") {
    return fail(400, "bad_request", "useGroqTableFill must be a boolean");
  }
  const saved = await setGroqTableFillEnabled(db, body.useGroqTableFill, identity.actor);
  if (!saved) return fail(500, "internal_error", "Could not save extraction settings");
  return ok({ useGroqTableFill: body.useGroqTableFill });
}
