import { StatusBadge } from "@/components/studio/status-badge";
import { formatDateTime, formatNumber } from "@/lib/format";
import { dispositionTone, humanize, transportLabel } from "@/features/operations/labels";

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

function recordingTone(state: string): "success" | "warning" | "danger" | "neutral" {
  if (state === "available") return "success";
  if (state === "recording") return "warning";
  if (state === "failed") return "danger";
  return "neutral";
}

function speakerLabel(speaker: string): string {
  if (speaker === "user" || speaker === "caller") return "Caller";
  if (speaker === "assistant" || speaker === "agent") return "Agent";
  return humanize(speaker);
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
  const intelligenceState = intelligence.state === "pending"
    ? { label: "Pending", tone: "warning" as const }
    : intelligence.state === "available" && intelligence.result
      ? { label: "Available", tone: "success" as const }
      : { label: "Unavailable", tone: "neutral" as const };

  return (
    <article className="conversation-detail">
      <section aria-labelledby="conversation-overview-heading" className="form-panel operate-panel">
        <h2 className="operate-panel__title" id="conversation-overview-heading">Overview</h2>
        <dl className="detail-grid">
          <div><dt>Started</dt><dd className="technical-value">{formatDateTime(conversation.started_at)}</dd></div>
          <div><dt>Ended</dt><dd className="technical-value">{conversation.ended_at ? formatDateTime(conversation.ended_at) : "Not ended"}</dd></div>
          <div><dt>Transport</dt><dd>{transportLabel(conversation.transport_type)}</dd></div>
          <div><dt>Disposition</dt><dd><StatusBadge tone={dispositionTone(conversation.disposition)}>{humanize(conversation.disposition)}</StatusBadge></dd></div>
          <div><dt>Turns</dt><dd className="technical-value">{conversation.turn_count}</dd></div>
          <div><dt>End reason</dt><dd>{conversation.end_reason ? humanize(conversation.end_reason) : "Not reported"}</dd></div>
        </dl>
      </section>

      <div className="conversation-detail__grid">
        <section aria-labelledby="transcript-heading" className="form-panel operate-panel">
          <h2 className="operate-panel__title" id="transcript-heading">Transcript</h2>
          {conversation.transcript.length === 0 ? <p className="muted-copy">No transcript turns were retained.</p> : (
            <ol className="voice-transcript">
              {conversation.transcript.map((turn, index) => (
                <li className={speakerLabel(turn.speaker) === "Agent" ? "voice-transcript__line voice-transcript__line--agent" : "voice-transcript__line"} key={`${turn.start_ms}-${index}`}>
                  <span className="voice-transcript__speaker">{speakerLabel(turn.speaker)}</span>
                  <span>{turn.text}</span>
                </li>
              ))}
            </ol>
          )}
        </section>

        <div className="conversation-detail__side">
          <section aria-labelledby="recording-heading" className="form-panel operate-panel">
            <div className="operate-panel__heading">
              <h2 className="operate-panel__title" id="recording-heading">Recording</h2>
              <StatusBadge tone={recordingTone(conversation.recording.state)}>{humanize(conversation.recording.state)}</StatusBadge>
            </div>
            <p className="muted-copy">{recordingMessage(conversation.recording)}</p>
            {typeof conversation.recording.duration_sec === "number" ? (
              <p className="field-help">Duration: {formatNumber(conversation.recording.duration_sec)} seconds</p>
            ) : null}
          </section>

          <section aria-labelledby="intelligence-heading" className="form-panel operate-panel">
            <div className="operate-panel__heading">
              <h2 className="operate-panel__title" id="intelligence-heading">Post-call intelligence</h2>
              <StatusBadge tone={intelligenceState.tone}>{intelligenceState.label}</StatusBadge>
            </div>
            {intelligence.state === "pending" ? (
              <p className="muted-copy">Intelligence processing is pending. No result is available yet.</p>
            ) : intelligence.state !== "available" || !intelligence.result ? (
              <p className="muted-copy">Intelligence is not available for this conversation.</p>
            ) : (
              <div className="intelligence-result">
                {summary ? <p>{summary}</p> : <p className="muted-copy">No durable summary was produced.</p>}
                {intelligence.result.verification_issue_codes.length > 0 ? (
                  <p className="field-help">Verification issues: <span className="technical-value">{intelligence.result.verification_issue_codes.join(", ")}</span></p>
                ) : null}
                {intelligence.review?.state === "pending" ? (
                  <p className="inline-notice inline-notice--warning" role="status">Review required: a decision is pending.</p>
                ) : null}
                {intelligence.review && intelligence.review.state !== "pending" ? (
                  <p className="field-help">Review state: {humanize(intelligence.review.state)}</p>
                ) : null}
              </div>
            )}
          </section>
        </div>
      </div>
    </article>
  );
}
