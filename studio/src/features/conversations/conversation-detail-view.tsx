import type { ConversationDetailDto, ConversationIntelligenceDto, RecordingViewDto } from "./types";

function recordingMessage(recording: RecordingViewDto): string {
  switch (recording.state) {
    case "available": return "Recording available; access is gated.";
    case "recording": return "Recording is still being processed.";
    case "failed": return "Recording failed and is unavailable.";
    case "deleted": return "Recording was deleted according to its retention state.";
    case "consent_blocked": return "Recording was blocked by consent policy.";
    case "not_requested": return "Recording was not requested for this conversation.";
    default: return `Recording state: ${recording.state}.`;
  }
}

function summaryText(summary: Record<string, unknown> | null): string | null {
  if (!summary) return null;
  return typeof summary.text === "string" ? summary.text : null;
}

export function ConversationDetailView({
  conversation,
  intelligence,
}: {
  conversation: ConversationDetailDto;
  intelligence: ConversationIntelligenceDto;
}) {
  const summary = summaryText(intelligence.result?.summary ?? null);

  return (
    <article>
      <header>
        <h2>Conversation detail</h2>
        <p>{new Date(conversation.started_at).toLocaleString()} - {conversation.transport_type}</p>
        <p>{recordingMessage(conversation.recording)}</p>
      </header>

      <section aria-labelledby="transcript-heading">
        <h3 id="transcript-heading">Transcript</h3>
        {conversation.transcript.length === 0 ? <p>No transcript turns were retained.</p> : (
          <ol>
            {conversation.transcript.map((turn, index) => (
              <li key={`${turn.start_ms}-${index}`}><strong>{turn.speaker}</strong>: {turn.text}</li>
            ))}
          </ol>
        )}
      </section>

      <section aria-labelledby="intelligence-heading">
        <h3 id="intelligence-heading">Post-call intelligence</h3>
        {intelligence.state === "pending" ? (
          <p>Intelligence processing is pending. No result is available yet.</p>
        ) : intelligence.state !== "available" || !intelligence.result ? (
          <p>Intelligence is not available for this conversation.</p>
        ) : (
          <>
            {summary ? <p>{summary}</p> : <p>No durable summary was produced.</p>}
            {intelligence.result.verification_issue_codes.length > 0 && (
              <p>Verification issues: {intelligence.result.verification_issue_codes.join(", ")}</p>
            )}
            {intelligence.review?.state === "pending" && <p role="status">Review required: a decision is pending.</p>}
            {intelligence.review && intelligence.review.state !== "pending" && (
              <p>Review state: {intelligence.review.state}</p>
            )}
          </>
        )}
      </section>
    </article>
  );
}
