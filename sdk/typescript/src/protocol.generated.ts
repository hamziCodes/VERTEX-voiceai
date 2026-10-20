/** Generated from sdk/shared/event_schema.json. Do not edit. */

export const PROTOCOL_VERSION = '1.0.0' as const;
export const SUPPORTED_PROTOCOL_RANGE = '>=1.0.0 <2.0.0' as const;

export type RealtimeEventType =
  | 'protocol.hello'
  | 'session.ready'
  | 'control.ping'
  | 'control.pong'
  | 'text.turn'
  | 'transcript.partial'
  | 'transcript.final'
  | 'transcript'
  | 'audio.start'
  | 'audio.end'
  | 'control.playback_started'
  | 'control.barge_in'
  | 'control.clear_audio'
  | 'control.clear_audio_ack'
  | 'control.playback_drained'
  | 'assistant.played_text_commit'
  | 'metric.latency'
  | 'session.token_expiring'
  | 'session.close'
  | 'error'
  | 'degraded';

export interface RealtimeEvent<
  T extends Record<string, unknown> = Record<string, unknown>
> {
  protocol_version: typeof PROTOCOL_VERSION;
  event_id: string;
  sequence: number;
  event_type: RealtimeEventType;
  timestamp_ms: number;
  payload: T;
}
