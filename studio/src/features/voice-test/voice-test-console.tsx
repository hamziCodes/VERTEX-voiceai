"use client";

import { useEffect, useRef, useState } from "react";

import { StatusBadge } from "@/components/studio/status-badge";

import { browserVoiceSupported, createBrowserVoiceRuntime, VoiceWorkerSetupError } from "./sdk-runtime";
import type { ConnectionState, MintVoiceSession, VoiceRuntime, VoiceRuntimeFactory, VoiceTestMode } from "./types";

interface TranscriptLine {
  id: number;
  speaker: "user" | "agent";
  text: string;
}

const MODE_TONE: Record<VoiceTestMode, "neutral" | "info" | "success"> = {
  disabled: "neutral",
  offline: "info",
  mock: "info",
  live: "success",
};

const MODE_LABEL: Record<VoiceTestMode, string> = {
  disabled: "Live disabled",
  offline: "Offline mode",
  mock: "Mock mode",
  live: "Live mode",
};

function metricValue(metrics: Record<string, unknown>, key: string): string {
  const durations = metrics.durations_ms;
  const value = durations && typeof durations === "object"
    ? (durations as Record<string, unknown>)[key]
    : undefined;
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value)} ms` : "Not measured";
}

export function VoiceTestConsole({
  agentId,
  agentName,
  canStart,
  mintSession,
  mode = "mock",
  runtimeFactory = createBrowserVoiceRuntime,
  browserSupported,
}: {
  agentId: string;
  agentName: string;
  canStart: boolean;
  mintSession: MintVoiceSession;
  mode?: VoiceTestMode;
  runtimeFactory?: VoiceRuntimeFactory;
  browserSupported?: boolean;
}) {
  const supported = browserSupported ?? browserVoiceSupported();
  const [connection, setConnection] = useState<ConnectionState>("disconnected");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [metrics, setMetrics] = useState<Record<string, unknown>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [audioReceived, setAudioReceived] = useState(false);
  const [starting, setStarting] = useState(false);
  const runtimeRef = useRef<VoiceRuntime | null>(null);
  const operationRef = useRef(0);
  const mountedRef = useRef(true);
  const lineId = useRef(0);

  const stop = () => {
    operationRef.current += 1;
    const runtime = runtimeRef.current;
    runtimeRef.current = null;
    if (runtime) runtime.stop();
    setConnection("disconnected");
    setStarting(false);
  };

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      operationRef.current += 1;
      const runtime = runtimeRef.current;
      runtimeRef.current = null;
      runtime?.stop();
    };
  }, []);

  async function start() {
    if (!canStart || !supported || starting || runtimeRef.current) return;
    const operation = operationRef.current + 1;
    operationRef.current = operation;
    setStarting(true);
    setError("");
    setMessage("");
    setTranscript([]);
    setMetrics({});
    setAudioReceived(false);
    const result = await mintSession(agentId);
    if (!mountedRef.current || operation !== operationRef.current) return;
    if (result.state === "error") {
      setError(result.message);
      setStarting(false);
      return;
    }
    try {
      const isCurrent = () => mountedRef.current && operation === operationRef.current;
      const callbacks = {
        onConnection: (state: ConnectionState) => {
          if (!isCurrent()) return;
          if (state === "disconnected") runtimeRef.current = null;
          setConnection(state);
        },
        onTranscript: (speaker: "user" | "agent", text: string) => {
          if (!isCurrent() || !text.trim()) return;
          lineId.current += 1;
          const id = lineId.current;
          setTranscript((current) => [...current, { id, speaker, text }]);
        },
        onMetric: (value: Record<string, unknown>) => { if (isCurrent()) setMetrics(value); },
        onAudio: () => { if (isCurrent()) setAudioReceived(true); },
        onInterruption: () => { if (isCurrent()) setMessage("Playback cleared for interruption."); },
        onTokenExpiring: () => {
          if (!isCurrent()) return;
          setError("The test session expired. Start a new session.");
          queueMicrotask(stop);
        },
        onError: (value: string) => { if (isCurrent()) setError(value || "The voice session failed."); },
      };
      const runtime = await runtimeFactory(result, callbacks);
      if (!isCurrent()) {
        runtime.stop();
        return;
      }
      runtimeRef.current = runtime;
      await runtime.start();
      if (!isCurrent()) {
        if (runtimeRef.current === runtime) {
          runtimeRef.current = null;
          runtime.stop();
        }
        return;
      }
      setStarting(false);
    } catch (caught) {
      if (!mountedRef.current || operation !== operationRef.current) return;
      const failureMessage = caught instanceof DOMException && caught.name === "NotAllowedError"
        ? "Microphone permission was denied. Allow microphone access and try again."
        : caught instanceof VoiceWorkerSetupError || (caught instanceof Error && /worker mode|fixed mock transcript/i.test(caught.message))
          ? caught.message
          : "The voice worker is unavailable. Try again shortly.";
      stop();
      setError(failureMessage);
    }
  }

  const connectionLabel = starting ? "starting" : connection;
  const connectionTone = connectionLabel === "connected" ? "success" : connectionLabel === "disconnected" ? "neutral" : "warning";

  return (
    <section aria-labelledby="voice-test-title" className="voice-console">
      <section aria-label="Session status" className="form-panel voice-console__status">
        <div className="voice-console__heading">
          <div>
            <p className="screen-eyebrow">Voice test environment</p>
            <h2 id="voice-test-title">Test {agentName}</h2>
            <p className="muted-copy">This uses a short-lived session token. Provider keys never enter the browser.</p>
          </div>
          <StatusBadge tone={MODE_TONE[mode]}>{MODE_LABEL[mode]}</StatusBadge>
        </div>
        {!canStart ? <p className="inline-notice inline-notice--info">You have view-only access to test status.</p> : null}
        {!supported ? <p className="inline-notice inline-notice--danger" role="alert">This browser cannot run a microphone voice test. Use a current Chrome or Edge browser with microphone access.</p> : null}
        {error ? <p className="inline-notice inline-notice--danger" role="alert">{error}</p> : null}
        {message ? <p className="inline-notice inline-notice--info" role="status">{message}</p> : null}
        <div className="voice-console__controls">
          <p className="voice-console__connection">Connection: <StatusBadge tone={connectionTone}>{connectionLabel}</StatusBadge></p>
          <div className="voice-console__buttons">
            <button className="button button--primary" type="button" onClick={start} disabled={!canStart || !supported || starting || connection !== "disconnected"}>Start voice test</button>
            <button className="button button--secondary" type="button" onClick={stop} disabled={connection === "disconnected" && !starting}>End test</button>
          </div>
        </div>
      </section>

      <div className="voice-console__grid">
        <section aria-labelledby="transcript-title" className="form-panel">
          <div className="voice-console__panel-title">
            <h3 id="transcript-title">Transcript</h3>
            <StatusBadge tone={audioReceived ? "success" : "neutral"}>{audioReceived ? "Audio received" : "No agent audio yet"}</StatusBadge>
          </div>
          {transcript.length === 0 ? <p className="muted-copy">Speak after the session connects. Transcript lines will appear here.</p> : (
            <ol className="voice-transcript">
              {transcript.map((line) => (
                <li className={line.speaker === "user" ? "voice-transcript__line" : "voice-transcript__line voice-transcript__line--agent"} key={line.id}>
                  <span className="voice-transcript__speaker">{line.speaker === "user" ? "You" : agentName}</span>
                  <span>{line.text}</span>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section aria-labelledby="latency-title" className="form-panel">
          <div className="voice-console__panel-title">
            <h3 id="latency-title">Turn latency</h3>
          </div>
          <dl className="voice-metrics">
            <div><dt>Speech recognition</dt><dd>{metricValue(metrics, "stt_after_acoustic_end")}</dd></div>
            <div><dt>First model token</dt><dd>{metricValue(metrics, "llm_ttft")}</dd></div>
            <div><dt>First speech audio</dt><dd>{metricValue(metrics, "tts_ttfb")}</dd></div>
            <div><dt>Audible end to end</dt><dd>{metricValue(metrics, "user_perceived_e2e")}</dd></div>
          </dl>
          <p className="field-help">Latency remains unmeasured until the worker reports a completed turn.</p>
        </section>
      </div>
    </section>
  );
}
