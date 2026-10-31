export interface AudioStartPayload {
  turn_id: string;
  server_send_ms: number;
  clock_domain: 'server_monotonic_ms';
}

export interface AudioEndPayload {
  turn_id: string;
}

export interface PlaybackStartedPayload {
  kind: 'playback_started';
  turn_id: string;
  client_clock_domain: 'client_performance_ms';
  client_playback_started_ms: number;
  client_scheduled_playback_ms: number | null;
  audio_context_time_sec: number | null;
  prebuffer_ms: number | null;
  underrun: boolean | null;
}

export interface LatencyMetricPayload {
  kind: 'latency';
  schema_version: '1.0';
  session_id: string;
  turn_id: string;
  clock_domain: 'server_monotonic_ms';
  client_clock_domain: 'client_performance_ms';
  measurement_quality: 'incomplete' | 'playback_ack_only' | 'server_ack_upper_bound' | 'excluded';
  timestamps_ms: Record<string, number | null>;
  durations_ms: Record<string, number | null>;
  queue: Record<string, unknown>;
  missing_reasons: string[];
}

export interface ClearAudioPayload {
  turn_id: string | null;
  sequence: number;
  reason: string;
}

export interface PlaybackDrainedPayload {
  turn_id: string;
  played_audio_ms: number;
}

export interface PlayedTextCommitPayload {
  turn_id: string;
  text: string;
  played_audio_ms: number;
  complete: boolean;
}
