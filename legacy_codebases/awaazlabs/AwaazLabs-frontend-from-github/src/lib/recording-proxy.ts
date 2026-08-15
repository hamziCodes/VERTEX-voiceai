/** Same-origin proxy path for Retell-hosted recordings (avoids CSP/CORS blocks on external .wav URLs). */
export function recordingProxyUrl(callId: string): string {
  return `/api/recording?callId=${encodeURIComponent(callId)}`;
}

export function hasRecordingSource(callId: string, upstreamUrl: string | null | undefined): boolean {
  return Boolean(callId.trim() && upstreamUrl?.trim());
}
