/**
 * Official UCVE Sovereign Voice Client (TypeScript / Browser).
 */

import type { AudioStartPayload } from './events';

export interface UCVEVoiceClientOptions {
  wsUrl?: string;
  sttProvider?: string;
  llmProvider?: string;
  ttsProvider?: string;
  onTranscript?: (speaker: 'user' | 'agent', text: string) => void;
  onAudio?: (pcm16: Int16Array) => void;
  onAudioStart?: (event: AudioStartPayload) => void;
  onMetric?: (metric: Record<string, unknown>) => void;
  onError?: (err: Error) => void;
  [key: string]: unknown;
}

export class UCVEVoiceClient {
  public readonly token: string;
  public readonly wsUrl: string;
  public readonly options: UCVEVoiceClientOptions;
  private ws: WebSocket | null = null;
  public static readonly versionManifest = {
    apiVersion: '1.0.0',
    eventSchemaVersion: '1.0.0',
    minServerVersion: '0.1.0',
  };

  constructor(token: string, options: UCVEVoiceClientOptions = {}) {
    // Strict zero-secret check
    for (const forbidden of ['apiKey', 'api_key', 'secret', 'privateKey']) {
      if (options && (forbidden in options || options[forbidden])) {
        throw new Error(
          `Client SDK must never accept raw '${forbidden}'. Mint an ephemeral session token on your host backend instead.`
        );
      }
    }

    if (!token || !token.trim()) {
      throw new Error('An ephemeral session token is required to initialize UCVEVoiceClient.');
    }

    this.token = token.trim();
    this.options = options;
    this.wsUrl = (options.wsUrl || 'ws://localhost:8081/ws/audio').trim();
  }

  public async connect(): Promise<void> {
    const sep = this.wsUrl.includes('?') ? '&' : '?';
    const params = new URLSearchParams({ token: this.token });
    if (this.options.sttProvider) params.set('stt_provider', this.options.sttProvider);
    if (this.options.llmProvider) params.set('llm_provider', this.options.llmProvider);
    if (this.options.ttsProvider) params.set('tts_provider', this.options.ttsProvider);

    const fullUrl = `${this.wsUrl}${sep}${params.toString()}`;

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(fullUrl);
        this.ws.binaryType = 'arraybuffer';

        this.ws.onopen = () => {
          resolve();
        };

        this.ws.onerror = (err) => {
          const errorObj = err instanceof Error ? err : new Error('WebSocket connection error');
          this.options.onError?.(errorObj);
          reject(errorObj);
        };

        this.ws.onmessage = (event: MessageEvent) => {
          if (event.data instanceof ArrayBuffer) {
            this.options.onAudio?.(new Int16Array(event.data));
            return;
          }

          if (typeof event.data === 'string') {
            try {
              const data = JSON.parse(event.data);
              const eventType = data.event_type || data.type;
              if (eventType === 'transcript') {
                const speaker = data.payload?.speaker || data.speaker || 'agent';
                const text = data.payload?.text || data.text || '';
                this.options.onTranscript?.(speaker, text);
              } else if (eventType === 'audio_start') {
                this.options.onAudioStart?.(data.payload as AudioStartPayload);
              } else if (eventType === 'metric') {
                this.options.onMetric?.(data.payload || data);
              } else if (eventType === 'error') {
                this.options.onError?.(new Error(data.payload?.message || data.error || 'Server error'));
              }
            } catch {
              // Non-JSON string frames ignored
            }
          }
        };
      } catch (err) {
        reject(err);
      }
    });
  }

  public sendAudioChunk(pcmBytes: ArrayBuffer | Uint8Array): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not open.');
    }
    this.ws.send(pcmBytes);
  }

  public emitPlaybackStarted(
    turnId: string,
    details: {
      clientScheduledPlaybackMs?: number;
      audioContextTimeSec?: number;
      prebufferMs?: number;
      underrun?: boolean;
    } = {}
  ): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    if (!turnId.trim()) throw new Error('turnId is required for playback correlation.');
    this.ws.send(
      JSON.stringify({
        event_type: 'control.playback_started',
        payload: {
          kind: 'playback_started',
          turn_id: turnId,
          client_clock_domain: 'client_performance_ms',
          client_playback_started_ms: performance.now(),
          client_scheduled_playback_ms: details.clientScheduledPlaybackMs ?? null,
          audio_context_time_sec: details.audioContextTimeSec ?? null,
          prebuffer_ms: details.prebufferMs ?? null,
          underrun: details.underrun ?? null,
        },
      })
    );
  }

  public sendBargeIn(rms = 0.08): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(
      JSON.stringify({
        event_type: 'control.barge_in',
        payload: { rms, t: Date.now() },
      })
    );
  }

  public disconnect(): void {
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onerror = null;
      this.ws.close();
      this.ws = null;
    }
  }
}
