/**
 * Official UCVE Sovereign Voice Client (TypeScript / Browser).
 */

export interface UCVEVoiceClientOptions {
  wsUrl?: string;
  sttProvider?: string;
  llmProvider?: string;
  ttsProvider?: string;
  onTranscript?: (speaker: 'user' | 'agent', text: string) => void;
  onAudio?: (pcm16: Int16Array) => void;
  onMetric?: (metric: Record<string, unknown>) => void;
  onError?: (err: Error) => void;
  [key: string]: unknown;
}

export class UCVEVoiceClient {
  public readonly token: string;
  public readonly wsUrl: string;
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
    this.wsUrl = (options.wsUrl || 'ws://localhost:8081/ws/audio').trim();
  }

  public async connect(): Promise<void> {
    const sep = this.wsUrl.includes('?') ? '&' : '?';
    const fullUrl = `${this.wsUrl}${sep}token=${encodeURIComponent(this.token)}`;
    this.ws = new WebSocket(fullUrl);
    this.ws.binaryType = 'arraybuffer';
  }

  public sendAudioChunk(pcmBytes: ArrayBuffer | Uint8Array): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not open.');
    }
    this.ws.send(pcmBytes);
  }

  public emitPlaybackStarted(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(
      JSON.stringify({
        event_type: 'control.playback_started',
        payload: { t: Date.now(), kind: 'playback_started' },
      })
    );
  }

  public disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
