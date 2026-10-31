"use client";

import { UCVEVoiceClient } from "@ucve/voice-sdk";

import type { ReadyVoiceSession, VoiceCallbacks, VoiceRuntime, VoiceRuntimeFactory } from "./types";

const SAMPLE_RATE = 16_000;

function pcm16(samples: Float32Array): Int16Array {
  const output = new Int16Array(samples.length);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index] ?? 0));
    output[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return output;
}

class BrowserAudioSession {
  private context: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private playback = new Set<AudioBufferSourceNode>();
  private playbackAckTimers = new Set<ReturnType<typeof setTimeout>>();
  private scheduledSegments: Array<{ start: number; end: number }> = [];
  private nextPlaybackAt = 0;
  private currentTurnId: string | null = null;
  private firstChunk = true;
  private drainTimer: ReturnType<typeof setTimeout> | null = null;
  private agentSpeaking = false;
  private lastBargeInAt = 0;
  private stopped = false;

  constructor(private readonly sendAudio: (chunk: Int16Array) => void, private readonly bargeIn: (rms: number) => void) {}

  async start(): Promise<void> {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }, video: false });
    this.stream = stream;
    if (this.stopped) {
      this.stop();
      throw new DOMException("Voice session was stopped.", "AbortError");
    }
    try {
      const context = new AudioContext({ sampleRate: SAMPLE_RATE });
      this.context = context;
      await context.resume();
      if (this.stopped) {
        this.stop();
        throw new DOMException("Voice session was stopped.", "AbortError");
      }
      this.source = context.createMediaStreamSource(stream);
      this.processor = context.createScriptProcessor(2048, 1, 1);
      this.processor.onaudioprocess = (event) => {
        const samples = event.inputBuffer.getChannelData(0);
        this.sendAudio(pcm16(samples));
        if (!this.agentSpeaking) return;
        const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / Math.max(1, samples.length));
        const now = performance.now();
        if (rms >= 0.08 && now - this.lastBargeInAt > 500) {
          this.lastBargeInAt = now;
          this.bargeIn(rms);
        }
      };
      this.source.connect(this.processor);
      this.processor.connect(this.context.destination);
    } catch (error) {
      this.stop();
      throw error;
    }
  }

  audioStarted(turnId: string): void {
    if (this.drainTimer) clearTimeout(this.drainTimer);
    this.drainTimer = null;
    this.agentSpeaking = true;
    this.nextPlaybackAt = 0;
    this.scheduledSegments = [];
    this.currentTurnId = turnId;
    this.firstChunk = true;
  }

  play(chunk: Int16Array, onStarted: (details: { turnId: string; scheduledPerformanceMs: number; audioContextTimeSec: number }) => void): void {
    const context = this.context;
    const turnId = this.currentTurnId;
    if (!context || context.state === "closed" || !turnId || this.stopped) return;
    const buffer = context.createBuffer(1, chunk.length, SAMPLE_RATE);
    const channel = buffer.getChannelData(0);
    for (let index = 0; index < chunk.length; index += 1) channel[index] = (chunk[index] ?? 0) / 0x8000;
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    source.onended = () => this.playback.delete(source);
    this.playback.add(source);
    const startAt = Math.max(context.currentTime + 0.02, this.nextPlaybackAt);
    const durationSeconds = chunk.length / SAMPLE_RATE;
    this.nextPlaybackAt = startAt + durationSeconds;
    this.scheduledSegments.push({ start: startAt, end: this.nextPlaybackAt });
    source.start(startAt);
    const scheduledPerformanceMs = performance.now() + Math.max(0, startAt - context.currentTime) * 1000;
    if (this.firstChunk) {
      const delayMs = Math.max(0, (startAt - context.currentTime) * 1000);
      const timer = setTimeout(() => {
        this.playbackAckTimers.delete(timer);
        if (!this.stopped && this.currentTurnId === turnId) {
          onStarted({ turnId, scheduledPerformanceMs, audioContextTimeSec: startAt });
        }
      }, delayMs);
      this.playbackAckTimers.add(timer);
    }
    this.firstChunk = false;
  }

  drain(turnId: string, callback: (playedAudioMs: number) => void): void {
    const context = this.context;
    if (!context || turnId !== this.currentTurnId) return;
    if (this.drainTimer) clearTimeout(this.drainTimer);
    const delayMs = Math.max(0, (this.nextPlaybackAt - context.currentTime) * 1000);
    this.drainTimer = setTimeout(() => {
      this.drainTimer = null;
      this.agentSpeaking = false;
      this.currentTurnId = null;
      const playedAudioMs = this.scheduledSegments.reduce((total, segment) => total + (segment.end - segment.start) * 1000, 0);
      callback(Math.max(0, Math.round(playedAudioMs)));
    }, delayMs);
  }

  clear(): number {
    const now = this.context?.currentTime ?? 0;
    const playedMs = this.scheduledSegments.reduce(
      (total, segment) => total + Math.max(0, Math.min(now, segment.end) - segment.start) * 1000,
      0,
    );
    for (const source of this.playback) {
      try { source.stop(); } catch { /* already stopped */ }
    }
    this.playback.clear();
    if (this.drainTimer) clearTimeout(this.drainTimer);
    this.drainTimer = null;
    for (const timer of this.playbackAckTimers) clearTimeout(timer);
    this.playbackAckTimers.clear();
    this.agentSpeaking = false;
    this.nextPlaybackAt = 0;
    this.scheduledSegments = [];
    this.currentTurnId = null;
    this.firstChunk = true;
    return Math.max(0, playedMs);
  }

  stop(): void {
    this.stopped = true;
    this.clear();
    if (this.processor) this.processor.onaudioprocess = null;
    this.processor?.disconnect();
    this.source?.disconnect();
    for (const track of this.stream?.getTracks() ?? []) track.stop();
    void this.context?.close();
    this.processor = null;
    this.source = null;
    this.stream = null;
    this.context = null;
  }
}

export function browserVoiceSupported(): boolean {
  return typeof window !== "undefined" && typeof WebSocket !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia) && typeof AudioContext !== "undefined";
}

export function validateWorkerMode(mode: ReadyVoiceSession["mode"], metric: Record<string, unknown>): string | null {
  if (metric.kind !== "session_ready") return null;
  const providerMode = metric.provider_mode;
  const transcriptMode = metric.stt_transcript_mode;
  const expectedProvider = mode === "live" ? "live" : "mock";
  if (providerMode !== expectedProvider) return `The voice worker mode does not match ${mode === "live" ? "Live" : mode === "mock" ? "Mock" : "Offline"} mode. Testing was stopped.`;
  if (mode === "mock" && transcriptMode !== "fixed_mock") return "Mock mode requires a fixed mock transcript, but this worker has mock speech disabled.";
  return null;
}

async function createRuntime(session: ReadyVoiceSession, callbacks: VoiceCallbacks): Promise<VoiceRuntime> {
  // Declared before the SDK so its callbacks can share the same audio session.
  // eslint-disable-next-line prefer-const
  let audio: BrowserAudioSession;
  let stopped = false;
  let audioSendEnabled = false;
  let runtimeStatusSettled = false;
  let resolveRuntimeStatus!: () => void;
  let rejectRuntimeStatus!: (error: Error) => void;
  const runtimeStatus = new Promise<void>((resolve, reject) => {
    resolveRuntimeStatus = resolve;
    rejectRuntimeStatus = reject;
  });
  let shutdown = () => undefined;
  const client = new UCVEVoiceClient(session.token, {
    wsUrl: session.wsUrl,
    maxConnectAttempts: 1,
    onTranscript: callbacks.onTranscript,
    onMetric: (metric) => {
      const mismatch = validateWorkerMode(session.mode, metric);
      if (metric.kind === "session_ready" && !runtimeStatusSettled) {
        runtimeStatusSettled = true;
        if (mismatch) {
          callbacks.onError(mismatch);
          rejectRuntimeStatus(new Error(mismatch));
          shutdown();
          return;
        }
        resolveRuntimeStatus();
        return;
      }
      callbacks.onMetric(metric);
    },
    onAudioStart: (event) => audio.audioStarted(event.turn_id),
    onAudio: (chunk) => {
      audio.play(chunk, (scheduled) => {
        client.emitPlaybackStarted(scheduled.turnId, {
          clientScheduledPlaybackMs: scheduled.scheduledPerformanceMs,
          audioContextTimeSec: scheduled.audioContextTimeSec,
          prebufferMs: 20,
        });
      });
      callbacks.onAudio();
    },
    onAudioEnd: (event) => audio.drain(event.turn_id, (playedAudioMs) => client.emitPlaybackDrained(event.turn_id, playedAudioMs)),
    onClearAudio: () => { callbacks.onInterruption(); return audio.clear(); },
    onTokenExpiring: callbacks.onTokenExpiring,
    onError: (error) => callbacks.onError(error.message),
    onClose: () => {
      if (!runtimeStatusSettled) {
        runtimeStatusSettled = true;
        rejectRuntimeStatus(new Error("The voice worker disconnected before reporting its runtime mode."));
      } else if (!stopped) {
        callbacks.onError("The voice worker disconnected. Start a new session to continue.");
      }
      shutdown();
    },
  });
  audio = new BrowserAudioSession(
    (chunk) => {
      if (audioSendEnabled) client.sendAudioChunk(new Uint8Array(chunk.buffer, chunk.byteOffset, chunk.byteLength));
    },
    (rms) => {
      if (audioSendEnabled) client.sendBargeIn(rms);
    },
  );
  shutdown = () => {
    if (stopped) return;
    stopped = true;
    audioSendEnabled = false;
    audio.stop();
    client.disconnect();
    callbacks.onConnection("disconnected");
  };
  return {
    async start() {
      callbacks.onConnection("connecting");
      await audio.start();
      if (stopped) return;
      await client.connect();
      await Promise.race([
        runtimeStatus,
        new Promise<never>((_, reject) => setTimeout(() => reject(new Error("The voice worker did not report its runtime mode.")), 3_000)),
      ]);
      if (stopped) return;
      audioSendEnabled = true;
      callbacks.onConnection("connected");
    },
    stop: shutdown,
  };
}

export const createBrowserVoiceRuntime: VoiceRuntimeFactory = createRuntime;
