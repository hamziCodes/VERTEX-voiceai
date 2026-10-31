export type VoiceTestMode = "disabled" | "offline" | "mock" | "live";
export type ConnectionState = "connecting" | "connected" | "disconnected";

export interface ReadyVoiceSession {
  state: "ready";
  token: string;
  wsUrl: string;
  ttlSec: number;
  mode: Exclude<VoiceTestMode, "disabled">;
}

export type VoiceSessionResult = ReadyVoiceSession | {
  state: "error";
  code: "permission_denied" | "quota_exceeded" | "worker_unavailable" | "live_disabled" | "session_expired" | "invalid_agent";
  message: string;
};

export interface VoiceCallbacks {
  onConnection(state: ConnectionState): void;
  onTranscript(speaker: "user" | "agent", text: string): void;
  onMetric(metric: Record<string, unknown>): void;
  onAudio(): void;
  onInterruption(): void;
  onTokenExpiring(): void;
  onError(message: string): void;
}

export interface VoiceRuntime {
  start(): Promise<void>;
  stop(): void;
}

export type VoiceRuntimeFactory = (
  session: ReadyVoiceSession,
  callbacks: VoiceCallbacks,
) => Promise<VoiceRuntime>;

export type MintVoiceSession = (agentId: string) => Promise<VoiceSessionResult>;
