// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { loadAgent, requireWorkspace } = vi.hoisted(() => ({ loadAgent: vi.fn(), requireWorkspace: vi.fn() }));
vi.mock("next/navigation", () => ({ notFound: vi.fn(), usePathname: () => "/agents/11111111-1111-4111-8111-111111111111/test" }));
vi.mock("@/features/agents/data", () => ({ loadAgent }));
vi.mock("@/features/voice-test/actions", () => ({ mintVoiceSessionAction: vi.fn() }));
vi.mock("@/features/voice-test/config", () => ({ configuredVoiceTestMode: () => "mock" }));
vi.mock("@/auth/workspace", async () => {
  const permissions = await import("@/auth/workspace-permissions");
  return { hasWorkspaceCapability: permissions.hasWorkspaceCapability, requireWorkspace };
});

import AgentTestPage from "@/app/(studio)/agents/[agentId]/test/page";
import { VoiceTestConsole } from "@/features/voice-test/voice-test-console";
import { readyTimeoutMs, validateWorkerMode, workerSetupMessage } from "@/features/voice-test/sdk-runtime";
import type { VoiceRuntime, VoiceRuntimeFactory } from "@/features/voice-test/types";

const session = {
  state: "ready" as const,
  token: "ephemeral-test-token",
  wsUrl: "ws://offline.test/ws/audio",
  ttlSec: 120,
  mode: "mock" as const,
};

function runtimeFactory(runtime: Partial<VoiceRuntime> = {}): VoiceRuntimeFactory {
  return vi.fn(async (_session, callbacks) => ({
    start: vi.fn(async () => {
      callbacks.onConnection("connected");
      callbacks.onTranscript("user", "Where is my order?");
      callbacks.onTranscript("agent", "I can help with that.");
      callbacks.onMetric({ durations_ms: { stt_after_acoustic_end: 210, llm_ttft: 145, tts_ttfb: 98, user_perceived_e2e: 690 } });
      callbacks.onAudio();
    }),
    stop: vi.fn(),
    ...runtime,
  }));
}

afterEach(cleanup);

describe("browser voice test", () => {
  it("rejects worker modes that contradict the visible environment badge", () => {
    expect(validateWorkerMode("mock", { kind: "session_ready", provider_mode: "mock", stt_transcript_mode: "fixed_mock" })).toBeNull();
    expect(validateWorkerMode("offline", { kind: "session_ready", provider_mode: "mock", stt_transcript_mode: "disabled" })).toBeNull();
    expect(validateWorkerMode("live", { kind: "session_ready", provider_mode: "live", stt_transcript_mode: "live" })).toBeNull();
    expect(validateWorkerMode("mock", { kind: "session_ready", provider_mode: "live", stt_transcript_mode: "live" })).toMatch(/does not match Mock mode/);
    expect(validateWorkerMode("mock", { kind: "session_ready", provider_mode: "mock", stt_transcript_mode: "disabled" })).toMatch(/fixed mock transcript/);
  });

  it("explains a worker setup refusal instead of calling the worker unavailable", () => {
    expect(workerSetupMessage({ code: "PROVIDER_CREDENTIAL_MISSING" }, "x")).toMatch(/no API key configured/);
    expect(workerSetupMessage({ code: "PROVIDER_SETUP_FAILED" }, "x")).toMatch(/could not be prepared/);
    expect(workerSetupMessage({ code: "SOMETHING_ELSE" }, "Worker said no.")).toBe("Worker said no.");
  });

  it("gives live sessions time to bind real providers before session_ready", () => {
    expect(readyTimeoutMs("live")).toBeGreaterThanOrEqual(10_000);
    expect(readyTimeoutMs("mock")).toBe(3_000);
    expect(readyTimeoutMs("offline")).toBe(3_000);
  });

  it("shows the environment before start and renders mock transcript, audio, and latency", async () => {
    render(<VoiceTestConsole agentId="11111111-1111-4111-8111-111111111111" agentName="Store assistant" canStart mintSession={vi.fn().mockResolvedValue(session)} runtimeFactory={runtimeFactory()} browserSupported />);
    expect(screen.getByText("Mock mode")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Start voice test" }));
    await waitFor(() => expect(screen.getByText("Where is my order?")).toBeVisible());
    expect(screen.getByText("I can help with that.")).toBeVisible();
    expect(screen.getByText("690 ms")).toBeVisible();
    expect(screen.getByText("Audio received")).toBeVisible();
  });

  it.each([
    ["permission_denied", "You do not have permission to start a voice test."],
    ["quota_exceeded", "Your workspace has reached its active-session limit."],
    ["worker_unavailable", "The voice worker is unavailable. Try again shortly."],
    ["live_disabled", "Live voice testing is disabled in this environment."],
  ])("renders typed %s failures", async (code, message) => {
    render(<VoiceTestConsole agentId="11111111-1111-4111-8111-111111111111" agentName="Store assistant" canStart mintSession={vi.fn().mockResolvedValue({ state: "error", code, message })} runtimeFactory={runtimeFactory()} browserSupported />);
    fireEvent.click(screen.getByRole("button", { name: "Start voice test" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(message));
  });

  it("reports unsupported browsers without requesting a session", () => {
    const mint = vi.fn();
    render(<VoiceTestConsole agentId="11111111-1111-4111-8111-111111111111" agentName="Store assistant" canStart mintSession={mint} runtimeFactory={runtimeFactory()} browserSupported={false} />);
    expect(screen.getByRole("alert")).toHaveTextContent("This browser cannot run a microphone voice test.");
    expect(screen.getByRole("button", { name: "Start voice test" })).toBeDisabled();
    expect(mint).not.toHaveBeenCalled();
  });

  it.each([
    [new Error("connection refused"), "The voice worker is unavailable. Try again shortly."],
    [new DOMException("denied", "NotAllowedError"), "Microphone permission was denied. Allow microphone access and try again."],
  ])("cleans up when browser startup fails", async (failure, message) => {
    const stop = vi.fn();
    const factory: VoiceRuntimeFactory = vi.fn(async () => ({ start: vi.fn().mockRejectedValue(failure), stop }));
    render(<VoiceTestConsole agentId="11111111-1111-4111-8111-111111111111" agentName="Store assistant" canStart mintSession={vi.fn().mockResolvedValue(session)} runtimeFactory={factory} browserSupported />);
    fireEvent.click(screen.getByRole("button", { name: "Start voice test" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(message));
    expect(stop).toHaveBeenCalledTimes(1);
  });

  it("clears playback on barge-in and cleans up on token expiry and unmount", async () => {
    const stop = vi.fn();
    const factory: VoiceRuntimeFactory = vi.fn(async (_session, callbacks) => ({
      start: vi.fn(async () => {
        callbacks.onConnection("connected");
        callbacks.onInterruption();
        callbacks.onTokenExpiring();
      }),
      stop,
    }));
    const view = render(<VoiceTestConsole agentId="11111111-1111-4111-8111-111111111111" agentName="Store assistant" canStart mintSession={vi.fn().mockResolvedValue(session)} runtimeFactory={factory} browserSupported />);
    fireEvent.click(screen.getByRole("button", { name: "Start voice test" }));
    await waitFor(() => expect(screen.getByText("Playback cleared for interruption.")).toBeVisible());
    expect(screen.getByRole("alert")).toHaveTextContent("The test session expired. Start a new session.");
    await waitFor(() => expect(stop).toHaveBeenCalledTimes(1));
    view.unmount();
    expect(stop).toHaveBeenCalledTimes(1);
  });

  it("keeps viewers read-only", () => {
    render(<VoiceTestConsole agentId="11111111-1111-4111-8111-111111111111" agentName="Store assistant" canStart={false} mintSession={vi.fn()} runtimeFactory={runtimeFactory()} />);
    expect(screen.getByText("You have view-only access to test status.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Start voice test" })).toBeDisabled();
  });

  it("does not create a runtime when the user ends during session mint", async () => {
    let resolveMint!: (value: typeof session) => void;
    const mint = vi.fn(() => new Promise<typeof session>((resolve) => { resolveMint = resolve; }));
    const factory = runtimeFactory();
    render(<VoiceTestConsole agentId="11111111-1111-4111-8111-111111111111" agentName="Store assistant" canStart mintSession={mint} runtimeFactory={factory} browserSupported />);
    fireEvent.click(screen.getByRole("button", { name: "Start voice test" }));
    fireEvent.click(screen.getByRole("button", { name: "End test" }));
    resolveMint(session);
    await waitFor(() => expect(screen.getByText(/Connection:/)).toHaveTextContent("disconnected"));
    expect(factory).not.toHaveBeenCalled();
  });

  it("composes status, transcript and latency regions without inline styles", async () => {
    const { container } = render(<VoiceTestConsole agentId="11111111-1111-4111-8111-111111111111" agentName="Store assistant" canStart mintSession={vi.fn().mockResolvedValue(session)} runtimeFactory={runtimeFactory()} browserSupported />);

    expect(container.querySelectorAll("[style]")).toHaveLength(0);
    const status = screen.getByRole("region", { name: "Session status" });
    expect(within(status).getByText("Mock mode")).toBeVisible();
    expect(within(status).getByText(/Connection:/)).toHaveTextContent("disconnected");
    expect(within(screen.getByRole("region", { name: "Transcript" })).getByText("Speak after the session connects. Transcript lines will appear here.")).toBeVisible();
    const latency = screen.getByRole("region", { name: "Turn latency" });
    expect(within(latency).getAllByText("Not measured")).toHaveLength(4);

    fireEvent.click(screen.getByRole("button", { name: "Start voice test" }));
    await waitFor(() => expect(within(status).getByText(/Connection:/)).toHaveTextContent("connected"));
    const lines = within(screen.getByRole("region", { name: "Transcript" })).getAllByRole("listitem");
    expect(lines[0]).toHaveTextContent("You");
    expect(lines[1]).toHaveTextContent("Store assistant");
    expect(within(latency).getByText("690 ms")).toBeVisible();
  });
});

describe("browser voice test page", () => {
  it("uses the shared header and explains why a draft agent cannot start", async () => {
    requireWorkspace.mockResolvedValue({ session: { accessToken: "offline" }, membership: { tenant_id: "22222222-2222-4222-8222-222222222222", capabilities: ["session:read", "session:mint"] } });
    loadAgent.mockResolvedValue({ agent_id: "11111111-1111-4111-8111-111111111111", name: "Store assistant", is_published: false });

    render(await AgentTestPage({ params: Promise.resolve({ agentId: "11111111-1111-4111-8111-111111111111" }) }));

    expect(requireWorkspace).toHaveBeenCalledWith("session:read");
    expect(screen.getByRole("heading", { level: 1, name: "Browser voice test" })).toBeVisible();
    expect(screen.getByRole("navigation", { name: "Agent workspace" })).toBeVisible();
    expect(screen.getByText("This agent has no published version. Publish it before starting a test.")).toHaveAttribute("role", "alert");
    expect(screen.getByRole("button", { name: "Start voice test" })).toBeDisabled();
  });
});
