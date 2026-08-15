import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

const SETTINGS_ID = "default";

/** When true, Groq transcript extraction may write booking / VOB queue columns. */
export async function isGroqTableFillEnabled(db: SupabaseClient): Promise<boolean> {
  const env = (Deno.env.get("USE_GROQ_TABLE_FILL") ?? "").trim().toLowerCase();
  if (env === "false" || env === "0" || env === "no") return false;
  if (env === "true" || env === "1" || env === "yes") return true;

  const { data, error } = await db
    .from("dashboard_runtime_settings")
    .select("use_groq_table_fill")
    .eq("id", SETTINGS_ID)
    .maybeSingle();
  if (error !== null) {
    console.error("extraction-settings: read failed", error);
    return true;
  }
  return data?.use_groq_table_fill !== false;
}

export async function setGroqTableFillEnabled(
  db: SupabaseClient,
  enabled: boolean,
  updatedBy: string,
): Promise<boolean> {
  const { error } = await db.from("dashboard_runtime_settings").upsert({
    id: SETTINGS_ID,
    use_groq_table_fill: enabled,
    updated_at: new Date().toISOString(),
    updated_by: updatedBy,
  }, { onConflict: "id" });
  if (error !== null) {
    console.error("extraction-settings: write failed", error);
    return false;
  }
  return true;
}

export async function getRuntimeSettings(db: SupabaseClient): Promise<{ useGroqTableFill: boolean }> {
  return { useGroqTableFill: await isGroqTableFillEnabled(db) };
}
