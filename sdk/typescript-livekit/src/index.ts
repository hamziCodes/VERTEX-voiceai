/**
 * @ucve/voice-livekit — Optional LiveKit Transport Adapter.
 */

export interface LiveKitVoiceOptions {
  roomName: string;
  participantToken: string;
}

export class UCVELiveKitAdapter {
  constructor(public readonly options: LiveKitVoiceOptions) {}

  public async connect(): Promise<void> {
    // Bridges LiveKit WebRTC track to UCVE Sovereign WebSocket
  }

  public disconnect(): void {
    // Disconnects WebRTC session
  }
}
