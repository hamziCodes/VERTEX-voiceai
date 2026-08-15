// support-chat — patient-facing web chat API (Groq + Supabase persistence).
// Called by the customer-support-chat Next.js proxy with a shared secret.

import { admin } from "../_shared/supa.ts";
import { classifySupportChatMeta } from "../_shared/support-chat-meta.ts";
import { SUPPORT_CHAT_PROMPT } from "../_shared/support-chat-prompt.ts";

const GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions";
const DEFAULT_MODEL = "llama-3.3-70b-versatile";
const MAX_MESSAGES = 20;
const UPSTREAM_TIMEOUT_MS = 20000;

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type, x-support-chat-secret",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

type IncomingMessage = {
  role: "user" | "assistant";
  content: string;
};

function isIncomingMessage(value: unknown): value is IncomingMessage {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<IncomingMessage>;
  return (
    (candidate.role === "user" || candidate.role === "assistant") &&
    typeof candidate.content === "string" &&
    candidate.content.trim().length > 0
  );
}

function authenticate(req: Request): boolean {
  const want = Deno.env.get("SUPPORT_CHAT_SECRET") ?? Deno.env.get("DASHBOARD_API_SECRET") ?? "";
  if (!want) {
    console.error("support-chat: SUPPORT_CHAT_SECRET is not set; rejecting request");
    return false;
  }
  const got = req.headers.get("x-support-chat-secret") ?? "";
  return got === want;
}

async function defaultLocationId(db: ReturnType<typeof admin>): Promise<string | null> {
  const { data, error } = await db.from("locations").select("id").order("created_at", { ascending: true }).limit(1)
    .maybeSingle();
  if (error) {
    console.error("support-chat: location lookup failed", error);
    return null;
  }
  return data?.id ?? null;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  if (req.method !== "POST") {
    return json({ error: "Only POST is supported." }, 405);
  }
  if (!authenticate(req)) {
    return json({ error: "Unauthorized." }, 401);
  }

  try {
    const apiKey = Deno.env.get("GROQ_API_KEY");
    if (!apiKey) {
      return json({ error: "Missing GROQ_API_KEY." }, 500);
    }

    const body = (await req.json()) as { sessionId?: unknown; messages?: unknown };
    if (!Array.isArray(body.messages)) {
      return json({ error: "Request must include a messages array." }, 400);
    }

    const messages = body.messages
      .filter(isIncomingMessage)
      .slice(-MAX_MESSAGES)
      .map((message) => ({
        role: message.role,
        content: message.content.trim(),
      }));

    if (messages.length === 0 || messages[messages.length - 1].role !== "user") {
      return json({ error: "Send a customer message before requesting a response." }, 400);
    }

    const db = admin();
    let sessionId = typeof body.sessionId === "string" ? body.sessionId.trim() : "";

    if (sessionId) {
      const { data: existing, error } = await db
        .from("support_chat_sessions")
        .select("id")
        .eq("id", sessionId)
        .maybeSingle();
      if (error || !existing) sessionId = "";
    }

    if (!sessionId) {
      const locationId = await defaultLocationId(db);
      if (!locationId) {
        return json({ error: "No clinic location is configured." }, 500);
      }
      const { data: created, error } = await db
        .from("support_chat_sessions")
        .insert({
          location_id: locationId,
          channel: "web_chat",
          started_at: new Date().toISOString(),
          last_message_at: new Date().toISOString(),
        })
        .select("id")
        .single();
      if (error || !created) {
        console.error("support-chat: session create failed", error);
        return json({ error: "Could not start chat session." }, 500);
      }
      sessionId = created.id;
    }

    const lastUserMessage = messages[messages.length - 1];
    const { error: userInsertError } = await db.from("support_chat_messages").insert({
      session_id: sessionId,
      role: "patient",
      content: lastUserMessage.content,
    });
    if (userInsertError) {
      console.error("support-chat: user message insert failed", userInsertError);
      return json({ error: "Could not save your message." }, 500);
    }

    const groqResponse = await fetch(GROQ_CHAT_COMPLETIONS_URL, {
      method: "POST",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: Deno.env.get("GROQ_MODEL") || DEFAULT_MODEL,
        temperature: 0.2,
        max_tokens: 220,
        messages: [
          { role: "system", content: SUPPORT_CHAT_PROMPT },
          ...messages,
        ],
      }),
    });

    const data = await groqResponse.json();
    if (!groqResponse.ok) {
      const message = data?.error?.message || "Groq rejected the chat completion request.";
      return json({ error: message }, groqResponse.status);
    }

    const reply = data?.choices?.[0]?.message?.content;
    if (typeof reply !== "string" || reply.trim().length === 0) {
      return json({ error: "The model returned an empty response." }, 502);
    }
    const trimmedReply = reply.trim();

    const meta = await classifySupportChatMeta(messages, trimmedReply);

    const { error: assistantInsertError } = await db.from("support_chat_messages").insert({
      session_id: sessionId,
      role: "agent",
      content: trimmedReply,
      is_handoff_marker: meta.outcome === "escalated",
    });
    if (assistantInsertError) {
      console.error("support-chat: assistant message insert failed", assistantInsertError);
      return json({ error: "Could not save assistant reply." }, 500);
    }

    const { count } = await db
      .from("support_chat_messages")
      .select("id", { count: "exact", head: true })
      .eq("session_id", sessionId);

    const { data: sessionRow } = await db
      .from("support_chat_sessions")
      .select("patient_label")
      .eq("id", sessionId)
      .maybeSingle();

    const patientLabel = meta.patientLabel ?? sessionRow?.patient_label ?? null;
    const now = new Date().toISOString();

    const { error: sessionUpdateError } = await db
      .from("support_chat_sessions")
      .update({
        purpose: meta.purpose,
        outcome: meta.outcome,
        language: meta.language,
        patient_label: patientLabel,
        message_count: count ?? messages.length + 1,
        last_message_at: now,
        updated_at: now,
      })
      .eq("id", sessionId);

    if (sessionUpdateError) {
      console.error("support-chat: session update failed", sessionUpdateError);
    }

    return json({
      reply: trimmedReply,
      sessionId,
      purpose: meta.purpose,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      return json({ error: "The model request timed out. Please try again." }, 504);
    }
    const message = error instanceof Error ? error.message : "Unexpected error while creating the chat response.";
    return json({ error: message }, 500);
  }
});

function json(payload: Record<string, unknown>, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders },
  });
}
