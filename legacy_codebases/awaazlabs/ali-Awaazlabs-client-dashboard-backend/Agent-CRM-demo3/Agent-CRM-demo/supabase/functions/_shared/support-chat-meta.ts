const GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions";
const DEFAULT_MODEL = "llama-3.3-70b-versatile";

export const SUPPORT_CHAT_PURPOSES = [
  "general_support",
  "appointment_cancel",
  "appointment_book",
  "appointment_change",
  "missed_ai_call",
  "link_access",
  "privacy_question",
  "technical_issue",
  "clinical_question",
  "human_follow_up",
] as const;

export type SupportChatPurpose = (typeof SUPPORT_CHAT_PURPOSES)[number];

export const SUPPORT_CHAT_OUTCOMES = ["contained", "resolved", "escalated", "booked"] as const;
export type SupportChatOutcome = (typeof SUPPORT_CHAT_OUTCOMES)[number];

export interface SupportChatMeta {
  purpose: SupportChatPurpose;
  outcome: SupportChatOutcome;
  patientLabel: string | null;
  language: "en" | "es" | "other";
}

type ChatTurn = { role: "user" | "assistant"; content: string };

function isPurpose(value: string): value is SupportChatPurpose {
  return (SUPPORT_CHAT_PURPOSES as readonly string[]).includes(value);
}

function isOutcome(value: string): value is SupportChatOutcome {
  return (SUPPORT_CHAT_OUTCOMES as readonly string[]).includes(value);
}

function inferOutcomeFromReply(reply: string): SupportChatOutcome {
  const lower = reply.toLowerCase();
  if (
    lower.includes("pass this to the support team") ||
    lower.includes("i'll pass this") ||
    lower.includes("i will pass this")
  ) {
    return "escalated";
  }
  if (lower.includes("emergency services") || lower.includes("healthcare provider immediately")) {
    return "escalated";
  }
  return "contained";
}

function inferPurposeFromText(text: string): SupportChatPurpose {
  const lower = text.toLowerCase();
  if (lower.includes("cancel")) return "appointment_cancel";
  if (lower.includes("book") || lower.includes("schedule")) return "appointment_book";
  if (lower.includes("reschedule") || lower.includes("change my appointment")) return "appointment_change";
  if (lower.includes("missed") && lower.includes("call")) return "missed_ai_call";
  if (lower.includes("link") || lower.includes("form") || lower.includes("not opening")) return "link_access";
  if (lower.includes("privacy") || lower.includes("recording")) return "privacy_question";
  if (
    lower.includes("chest pain") ||
    lower.includes("medication") ||
    lower.includes("diagnosis") ||
    lower.includes("symptom")
  ) {
    return "clinical_question";
  }
  if (lower.includes("human") || lower.includes("real person") || lower.includes("speak to someone")) {
    return "human_follow_up";
  }
  if (
    lower.includes("error") ||
    lower.includes("not working") ||
    lower.includes("technical") ||
    lower.includes("transcript")
  ) {
    return "technical_issue";
  }
  return "general_support";
}

function parseMetaJson(raw: string): Partial<SupportChatMeta> | null {
  const trimmed = raw.trim();
  const start = trimmed.indexOf("{");
  const end = trimmed.lastIndexOf("}");
  if (start < 0 || end <= start) return null;
  try {
    const parsed = JSON.parse(trimmed.slice(start, end + 1)) as Record<string, unknown>;
    const purposeRaw = typeof parsed.purpose === "string" ? parsed.purpose : "";
    const outcomeRaw = typeof parsed.outcome === "string" ? parsed.outcome : "";
    const patientLabel = typeof parsed.patient_label === "string"
      ? parsed.patient_label.trim().slice(0, 80) || null
      : typeof parsed.patientLabel === "string"
      ? parsed.patientLabel.trim().slice(0, 80) || null
      : null;
    const languageRaw = typeof parsed.language === "string" ? parsed.language : "en";
    const language = languageRaw === "es" ? "es" : languageRaw === "other" ? "other" : "en";
    return {
      purpose: isPurpose(purposeRaw) ? purposeRaw : undefined,
      outcome: isOutcome(outcomeRaw) ? outcomeRaw : undefined,
      patientLabel,
      language,
    };
  } catch {
    return null;
  }
}

export async function classifySupportChatMeta(
  messages: ChatTurn[],
  assistantReply: string,
): Promise<SupportChatMeta> {
  const lastUser = [...messages].reverse().find((m) => m.role === "user")?.content ?? "";
  const fallback: SupportChatMeta = {
    purpose: inferPurposeFromText(lastUser),
    outcome: inferOutcomeFromReply(assistantReply),
    patientLabel: null,
    language: /[áéíóúñ¿¡]/i.test(lastUser) ? "es" : "en",
  };

  const apiKey = Deno.env.get("GROQ_API_KEY");
  if (!apiKey) return fallback;

  const transcript = messages
    .map((m) => `${m.role === "user" ? "Patient" : "Assistant"}: ${m.content}`)
    .join("\n");

  try {
    const response = await fetch(GROQ_CHAT_COMPLETIONS_URL, {
      method: "POST",
      signal: AbortSignal.timeout(8000),
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: Deno.env.get("GROQ_MODEL") || DEFAULT_MODEL,
        temperature: 0,
        max_tokens: 120,
        messages: [
          {
            role: "system",
            content:
              `Classify this patient support chat. Reply with JSON only, no markdown:
{"purpose":"<slug>","outcome":"<slug>","patient_label":<string or null>,"language":"en|es|other"}

purpose must be one of: ${SUPPORT_CHAT_PURPOSES.join(", ")}
outcome must be one of: ${SUPPORT_CHAT_OUTCOMES.join(", ")}
patient_label: first name only if the patient volunteered a name; otherwise null. Never invent a name.`,
          },
          {
            role: "user",
            content: `${transcript}\nAssistant: ${assistantReply}`,
          },
        ],
      }),
    });

    const data = await response.json();
    const content = data?.choices?.[0]?.message?.content;
    if (!response.ok || typeof content !== "string") return fallback;

    const parsed = parseMetaJson(content);
    if (!parsed) return fallback;

    return {
      purpose: parsed.purpose && isPurpose(parsed.purpose) ? parsed.purpose : fallback.purpose,
      outcome: parsed.outcome && isOutcome(parsed.outcome) ? parsed.outcome : fallback.outcome,
      patientLabel: parsed.patientLabel ?? null,
      language: parsed.language ?? fallback.language,
    };
  } catch {
    return fallback;
  }
}
