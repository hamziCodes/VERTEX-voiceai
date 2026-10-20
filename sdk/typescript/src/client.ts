/** Wavia v1 raw-WebSocket browser client. */

import type { AudioStartPayload, ClearAudioPayload, PlayedTextCommitPayload } from './events.js';
import {
  PROTOCOL_VERSION,
  type RealtimeEvent,
  type RealtimeEventType,
} from './protocol.generated.js';

export interface UCVEVoiceClientOptions {
  wsUrl?: string;
  allowDemoProviderOverrides?: boolean;
  demoProviderOverrides?: Partial<Record<'stt_provider' | 'llm_provider' | 'llm_model' | 'tts_provider' | 'tts_voice_id', string>>;
  maxConnectAttempts?: number;
  reconnectBackoffMs?: number;
  handshakeTimeoutMs?: number;
  onTranscript?: (speaker: 'user' | 'agent', text: string) => void;
  onAudio?: (pcm16: Int16Array) => void;
  onAudioStart?: (event: AudioStartPayload) => void;
  onBargeIn?: (event: Record<string, unknown>) => void;
  onClearAudio?: (event: ClearAudioPayload) => number | void | Promise<number | void>;
  onCancelPlayback?: () => void;
  onPlayedTextCommit?: (event: PlayedTextCommitPayload) => void;
  onMetric?: (metric: Record<string, unknown>) => void;
  onDegraded?: (event: Record<string, unknown>) => void;
  onTokenExpiring?: (event: Record<string, unknown>) => void;
  onError?: (err: Error, event?: Record<string, unknown>) => void;
  onClose?: (event: Record<string, unknown>) => void;
  [key: string]: unknown;
}

export class UCVEVoiceClient {
  public readonly token: string;
  public readonly wsUrl: string;
  public readonly options: UCVEVoiceClientOptions;
  private ws: WebSocket | null = null;
  private activeTurnId: string | null = null;
  private sequence = 0;
  private controlSequence = 0;
  private handshakeTimer: ReturnType<typeof setTimeout> | null = null;

  public static readonly versionManifest = {
    apiVersion: '1.0.0',
    eventSchemaVersion: PROTOCOL_VERSION,
    minServerVersion: '0.1.0',
  } as const;

  constructor(token: string, options: UCVEVoiceClientOptions = {}) {
    for (const forbidden of ['apiKey', 'api_key', 'secret', 'privateKey']) {
      if (forbidden in options) {
        throw new Error(`Client SDK must never accept raw '${forbidden}'. Mint an ephemeral session token on your host backend instead.`);
      }
    }
    if (!token?.trim()) throw new Error('An ephemeral session token is required to initialize UCVEVoiceClient.');
    if (options.demoProviderOverrides && !options.allowDemoProviderOverrides) {
      throw new Error('Provider overrides are demo-only; explicitly enable them only for a local demo.');
    }
    this.token = token.trim();
    this.options = options;
    this.wsUrl = (options.wsUrl || 'ws://localhost:8081/ws/audio').trim();
  }

  public get connectionUrl(): string {
    const url = new URL(this.wsUrl);
    url.searchParams.set('token', this.token);
    url.searchParams.set('protocol_version', PROTOCOL_VERSION);
    for (const [key, value] of Object.entries(this.options.demoProviderOverrides || {})) {
      if (value) url.searchParams.set(key, value);
    }
    return url.toString();
  }

  private buildEvent(eventType: RealtimeEventType, payload: Record<string, unknown>): RealtimeEvent {
    this.sequence += 1;
    return {
      protocol_version: PROTOCOL_VERSION,
      event_id: globalThis.crypto?.randomUUID?.() || `evt-${Date.now()}-${this.sequence}`,
      sequence: this.sequence,
      event_type: eventType,
      timestamp_ms: Date.now(),
      payload,
    };
  }

  public buildHelloEvent(): RealtimeEvent {
    return this.buildEvent('protocol.hello', {
      protocol_version: PROTOCOL_VERSION,
      sdk: { name: 'ucve-typescript', version: UCVEVoiceClient.versionManifest.apiVersion },
      capabilities: ['pcm16', 'barge_in', 'playback_ack'],
      resume: null,
    });
  }

  public async connect(): Promise<void> {
    const attempts = Math.max(1, Math.min(Number(this.options.maxConnectAttempts ?? 3), 5));
    const baseDelay = Math.max(0, Number(this.options.reconnectBackoffMs ?? 250));
    let lastError: unknown;
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        await this.connectOnce();
        return;
      } catch (error) {
        lastError = error;
        this.disconnect();
        if (attempt + 1 < attempts) await new Promise((resolve) => setTimeout(resolve, baseDelay * 2 ** attempt));
      }
    }
    throw lastError instanceof Error ? lastError : new Error('WebSocket connection failed');
  }

  private connectOnce(): Promise<void> {
    return new Promise((resolve, reject) => {
      const socket = new WebSocket(this.connectionUrl);
      this.ws = socket;
      socket.binaryType = 'arraybuffer';
      let negotiated = false;
      const fail = (error: Error) => {
        if (this.handshakeTimer) clearTimeout(this.handshakeTimer);
        this.handshakeTimer = null;
        this.options.onError?.(error);
        reject(error);
      };

      socket.onopen = () => {
        socket.send(JSON.stringify(this.buildHelloEvent()));
        this.handshakeTimer = setTimeout(
          () => fail(new Error('Protocol handshake timed out.')),
          Math.max(100, Number(this.options.handshakeTimeoutMs ?? 5000)),
        );
      };
      socket.onerror = () => fail(new Error('WebSocket connection error'));
      socket.onclose = (event) => {
        this.activeTurnId = null;
        this.options.onClose?.({ code: event.code, reason: event.reason, retryable: event.code >= 1011 });
        if (!negotiated) fail(new Error(event.reason || 'WebSocket closed during handshake'));
      };
      socket.onmessage = async (event: MessageEvent) => {
        if (event.data instanceof ArrayBuffer) {
          this.options.onAudio?.(new Int16Array(event.data));
          return;
        }
        if (typeof event.data !== 'string') return;
        let data: Record<string, any>;
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }
        const eventType = String(data.event_type || data.type || '');
        const payload = (data.payload || {}) as Record<string, any>;
        if (!negotiated) {
          if (eventType !== 'session.ready') {
            fail(new Error(String(payload.code || 'Protocol handshake failed')));
            return;
          }
          negotiated = true;
          if (this.handshakeTimer) clearTimeout(this.handshakeTimer);
          this.handshakeTimer = null;
          resolve();
          return;
        }
        await this.handleEvent(eventType, payload);
      };
    });
  }

  private async handleEvent(eventType: string, payload: Record<string, any>): Promise<void> {
    if (eventType === 'control.ping' || eventType === 'ping') {
      this.sendControl('control.pong', {});
    } else if (['transcript.final', 'transcript.partial', 'transcript'].includes(eventType)) {
      this.options.onTranscript?.(payload.speaker || 'agent', payload.text || '');
    } else if (eventType === 'audio.start' || eventType === 'audio_start') {
      this.activeTurnId = payload.turn_id || null;
      this.options.onAudioStart?.(payload as AudioStartPayload);
    } else if (eventType === 'control.barge_in' || eventType === 'barge_in') {
      this.options.onBargeIn?.(payload);
    } else if (eventType === 'control.clear_audio') {
      const reported = await this.options.onClearAudio?.(payload as ClearAudioPayload);
      this.cancelPlayback();
      this.sendControl('control.clear_audio_ack', {
        turn_id: payload.turn_id,
        sequence: payload.sequence,
        played_audio_ms: typeof reported === 'number' ? Math.max(0, reported) : 0,
      });
      this.activeTurnId = null;
    } else if (eventType === 'assistant.played_text_commit') {
      this.options.onPlayedTextCommit?.(payload as PlayedTextCommitPayload);
    } else if (eventType === 'metric.latency' || eventType === 'metric') {
      this.options.onMetric?.(payload);
    } else if (eventType === 'degraded') {
      this.options.onDegraded?.(payload);
    } else if (eventType === 'session.token_expiring') {
      this.options.onTokenExpiring?.(payload);
    } else if (eventType === 'error') {
      this.options.onError?.(new Error(String(payload.message || payload.code || 'Server error')), payload);
    } else if (eventType === 'session.close') {
      this.options.onClose?.(payload);
      this.disconnect();
    }
  }

  public sendAudioChunk(pcmBytes: ArrayBuffer | Uint8Array): void {
    this.requireOpen().send(pcmBytes);
  }

  public sendTextTurn(text: string): void {
    const cleaned = text.trim();
    if (!cleaned) throw new Error('text is required');
    this.requireOpen().send(JSON.stringify(this.buildEvent('text.turn', { text: cleaned })));
  }

  public emitPlaybackStarted(turnId: string, details: { clientScheduledPlaybackMs?: number; audioContextTimeSec?: number; prebufferMs?: number; underrun?: boolean } = {}): void {
    if (!turnId.trim()) throw new Error('turnId is required for playback correlation.');
    this.sendControl('control.playback_started', {
      kind: 'playback_started', turn_id: turnId, client_clock_domain: 'client_performance_ms',
      client_playback_started_ms: performance.now(), client_scheduled_playback_ms: details.clientScheduledPlaybackMs ?? null,
      audio_context_time_sec: details.audioContextTimeSec ?? null, prebuffer_ms: details.prebufferMs ?? null,
      underrun: details.underrun ?? null,
    });
  }

  public sendBargeIn(rms = 0.08): void {
    this.controlSequence += 1;
    this.sendControl('control.barge_in', { rms, t: Date.now(), turn_id: this.activeTurnId, sequence: this.controlSequence });
  }

  public emitPlaybackDrained(turnId: string, playedAudioMs: number): void {
    if (!turnId.trim()) throw new Error('turnId is required for playback correlation.');
    this.sendControl('control.playback_drained', { turn_id: turnId, played_audio_ms: Math.max(0, playedAudioMs) });
    if (this.activeTurnId === turnId) this.activeTurnId = null;
  }

  public cancelPlayback(): void {
    this.options.onCancelPlayback?.();
  }

  private requireOpen(): WebSocket {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) throw new Error('WebSocket is not open.');
    return this.ws;
  }

  private sendControl(eventType: RealtimeEventType, payload: Record<string, unknown>): void {
    this.requireOpen().send(JSON.stringify(this.buildEvent(eventType, payload)));
  }

  public disconnect(): void {
    if (this.handshakeTimer) clearTimeout(this.handshakeTimer);
    this.handshakeTimer = null;
    const socket = this.ws;
    this.ws = null;
    this.activeTurnId = null;
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      socket.close(1000, 'client disconnect');
    }
  }
}
