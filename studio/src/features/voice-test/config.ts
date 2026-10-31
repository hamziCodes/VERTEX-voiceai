import "server-only";

import type { VoiceTestMode } from "./types";

export function configuredVoiceTestMode(): VoiceTestMode {
  const value = process.env.WAVIA_VOICE_TEST_MODE?.trim().toLowerCase();
  return value === "offline" || value === "mock" || value === "live" ? value : "disabled";
}
