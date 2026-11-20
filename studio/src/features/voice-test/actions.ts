"use server";

import { z } from "zod";

import { requireWorkspace } from "@/auth/workspace";
import { ControlPlaneError, controlPlaneRequest } from "@/data/control-plane";
import { voiceSessionSchema } from "@/data/schema";

import { configuredVoiceTestMode } from "./config";
import type { VoiceSessionResult } from "./types";

const agentIdSchema = z.string().uuid();

function typedFailure(error: unknown): VoiceSessionResult {
  if (error instanceof ControlPlaneError) {
    if (error.status === 403) return { state: "error", code: "permission_denied", message: "You do not have permission to start a voice test." };
    if (error.status === 409 || error.status === 422) return { state: "error", code: "invalid_agent", message: "Publish a valid agent configuration before testing." };
    if (error.status === 429) return { state: "error", code: "quota_exceeded", message: "Your workspace has reached its active-session limit." };
    if (error.status === 401) return { state: "error", code: "session_expired", message: "Your Studio session expired. Sign in again." };
  }
  return { state: "error", code: "worker_unavailable", message: "The voice worker is unavailable. Try again shortly." };
}

export async function mintVoiceSessionAction(agentId: string): Promise<VoiceSessionResult> {
  const mode = configuredVoiceTestMode();
  if (mode === "disabled") return { state: "error", code: "live_disabled", message: "Live voice testing is disabled in this environment." };
  const { session, membership } = await requireWorkspace("session:mint");
  const parsed = agentIdSchema.safeParse(agentId);
  if (!parsed.success) return { state: "error", code: "invalid_agent", message: "Choose a valid agent to test." };
  try {
    const response = await controlPlaneRequest("/v1/studio/sessions", {
      method: "POST",
      json: { agent_id: parsed.data, test_mode: mode },
      schema: voiceSessionSchema,
      session,
      selectedTenantId: membership.tenant_id,
    });
    return { state: "ready", token: response.token, wsUrl: response.ws_url, ttlSec: response.ttl_sec, mode };
  } catch (error) {
    return typedFailure(error);
  }
}
