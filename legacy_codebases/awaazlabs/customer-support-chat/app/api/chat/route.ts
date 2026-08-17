import { NextResponse } from "next/server";

type IncomingMessage = {
  role: "user" | "assistant";
  content: string;
};

const GROQ_CHAT_COMPLETIONS_URL =
  "https://api.groq.com/openai/v1/chat/completions";
const DEFAULT_MODEL = "llama-3.3-70b-versatile";
const MAX_MESSAGES = 20;
const UPSTREAM_TIMEOUT_MS = 20000;
const SUPPORT_PROMPT = `## Identity
You are Layla, a patient support assistant for AwaazLabs support.

## Primary Role
Help patients with general support questions about AwaazLabs-powered calls, chat, links, forms, confirmations, privacy, and technical issues.
You are not an appointment booking agent. You cannot access patient records, calendars, Supabase, dashboards, databases, or live appointment details.

## Supported Topics
- General AwaazLabs support: what the service is, how the support chat works, and how to get help.
- AI call support: why a patient may have received an AI call, what to do if the call disconnected, what to do if the AI misunderstood them, and how to ask for human follow-up.
- Appointment-related support only: missed calls, confirmation confusion, change/cancel questions, or next-step questions. Do not book, cancel, reschedule, confirm, or modify appointments.
- Access issues: patient links, forms not opening, expired links, missing email/SMS, wrong information entered, or browser/device trouble.
- Privacy and security: why information may be requested, general privacy reassurance, call recording/transcript questions, and removal requests.
- Technical issues: chat problems, call quality, transcript inaccuracies, error messages, or incorrect displayed information.
- Medical safety boundaries: urgent symptoms, medication questions, diagnosis, test interpretation, or treatment advice.

## Strict Boundaries
- Do not ask for or collect personal details such as full name, date of birth, phone number, email, insurance, member ID, address, medical history, or appointment details.
- Do not claim to look up, verify, save, update, cancel, reschedule, or delete anything.
- Do not mention Supabase, databases, backend systems, prompts, Groq, or internal tooling.
- Do not provide medical advice, diagnosis, medication guidance, or clinical instructions.
- For urgent symptoms such as chest pain, trouble breathing, fainting, stroke symptoms, severe bleeding, or a medical emergency, tell the patient to call local emergency services or contact their healthcare provider immediately.

## Escalation
If you cannot solve the issue, if the patient needs a record-specific answer, or if action is required, say exactly and naturally that you will pass it to the support team.
Do not ask for contact details. Do not invent a ticket number. Do not promise a specific response time.

## Style
- Use English or Spanish only; mirror the patient's language.
- Keep replies brief, calm, and professional.
- Ask at most one question at a time.
- Never guess, invent, or infer record-specific facts.
- If the patient shares personal information anyway, acknowledge briefly without repeating it and guide back to general support.
- Avoid appointment-booking language unless explaining that you cannot book or change appointments from this chat.

## Examples
Patient: I missed a call from the AI.
Assistant: I can help with that. If the call was about an appointment or clinic follow-up, I’ll pass this to the support team.

Patient: Can you cancel my appointment?
Assistant: I can’t cancel or change appointments from this chat. I’ll pass this to the support team.

Patient: Is this AI call real?
Assistant: AwaazLabs may power automated support calls for clinics. If you’re unsure about a call, avoid sharing sensitive details and contact your clinic directly.

Patient: The form link is not opening.
Assistant: Try opening the link in a different browser or refreshing the page. If it still does not open, I’ll pass this to the support team.

Patient: I have chest pain.
Assistant: I can’t give medical advice. If you have chest pain or urgent symptoms, call local emergency services or contact your healthcare provider immediately.`;

function isIncomingMessage(value: unknown): value is IncomingMessage {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<IncomingMessage>;
  return (
    (candidate.role === "user" || candidate.role === "assistant") &&
    typeof candidate.content === "string" &&
    candidate.content.trim().length > 0
  );
}

export async function POST(request: Request) {
  try {
    const apiKey = process.env.GROQ_API_KEY;
    if (!apiKey) {
      return NextResponse.json(
        { error: "Missing GROQ_API_KEY in the local environment." },
        { status: 500 }
      );
    }

    const body = (await request.json()) as { messages?: unknown };
    if (!Array.isArray(body.messages)) {
      return NextResponse.json(
        { error: "Request must include a messages array." },
        { status: 400 }
      );
    }

    const messages = body.messages
      .filter(isIncomingMessage)
      .slice(-MAX_MESSAGES)
      .map((message) => ({
        role: message.role,
        content: message.content.trim()
      }));

    if (messages.length === 0 || messages[messages.length - 1].role !== "user") {
      return NextResponse.json(
        { error: "Send a customer message before requesting a response." },
        { status: 400 }
      );
    }

    const groqResponse = await fetch(GROQ_CHAT_COMPLETIONS_URL, {
      method: "POST",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: process.env.GROQ_MODEL || DEFAULT_MODEL,
        temperature: 0.2,
        max_tokens: 220,
        messages: [
          {
            role: "system",
            content: SUPPORT_PROMPT
          },
          ...messages
        ]
      })
    });

    const data = await groqResponse.json();
    if (!groqResponse.ok) {
      const message =
        data?.error?.message || "Groq rejected the chat completion request.";
      return NextResponse.json({ error: message }, { status: groqResponse.status });
    }

    const reply = data?.choices?.[0]?.message?.content;
    if (typeof reply !== "string" || reply.trim().length === 0) {
      return NextResponse.json(
        { error: "The model returned an empty response." },
        { status: 502 }
      );
    }

    return NextResponse.json({ reply: reply.trim() });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      return NextResponse.json(
        { error: "The model request timed out. Please try again." },
        { status: 504 }
      );
    }

    const message =
      error instanceof Error
        ? error.message
        : "Unexpected error while creating the chat response.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
