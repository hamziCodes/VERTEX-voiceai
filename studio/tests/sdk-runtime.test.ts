// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({ instances: [] as Array<{
  options: ClientOptions;
  connect: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
  sendAudioChunk: ReturnType<typeof vi.fn>;
  sendBargeIn: ReturnType<typeof vi.fn>;
  emitPlaybackStarted: ReturnType<typeof vi.fn>;
  emitPlaybackDrained: ReturnType<typeof vi.fn>;
}> }));

interface ClientOptions {
  onMetric(metric: Record<string, unknown>): void;
}

vi.mock("@ucve/voice-sdk", () => ({
  UCVEVoiceClient: class {
    readonly connect = vi.fn(async () => undefined);
    readonly disconnect = vi.fn();
    readonly sendAudioChunk = vi.fn();
    readonly sendBargeIn = vi.fn();
    readonly emitPlaybackStarted = vi.fn();
    readonly emitPlaybackDrained = vi.fn();

    constructor(_token: string, readonly options: ClientOptions) {
      sdk.instances.push(this);
    }
  },
}));

import { createBrowserVoiceRuntime } from "@/features/voice-test/sdk-runtime";

class FakeAudioContext {
  static resumeError: Error | null = null;
  static instances: FakeAudioContext[] = [];

  readonly destination = {};
  readonly close = vi.fn(async () => undefined);
  readonly resume = vi.fn(async () => {
    if (FakeAudioContext.resumeError) throw FakeAudioContext.resumeError;
  });
  readonly source = { connect: vi.fn(), disconnect: vi.fn() };
  readonly processor = {
    connect: vi.fn(),
    disconnect: vi.fn(),
    onaudioprocess: null as ((event: { inputBuffer: { getChannelData(channel: number): Float32Array } }) => void) | null,
  };
  currentTime = 0;
  state = "running";

  constructor() {
    FakeAudioContext.instances.push(this);
  }

  createMediaStreamSource() { return this.source; }
  createScriptProcessor() { return this.processor; }
}

function callbacks() {
  return {
    onConnection: vi.fn(), onTranscript: vi.fn(), onMetric: vi.fn(), onAudio: vi.fn(),
    onInterruption: vi.fn(), onTokenExpiring: vi.fn(), onError: vi.fn(),
  };
}

function readyMetric(client: (typeof sdk.instances)[number]) {
  client.options.onMetric({
    kind: "session_ready",
    provider_mode: "mock",
    stt_transcript_mode: "fixed_mock",
  });
}

describe("browser SDK runtime ownership", () => {
  beforeEach(() => {
    sdk.instances.length = 0;
    FakeAudioContext.instances.length = 0;
    FakeAudioContext.resumeError = null;
    vi.stubGlobal("AudioContext", FakeAudioContext);
  });

  afterEach(() => vi.unstubAllGlobals());

  it("stops a microphone stream that resolves after startup was cancelled", async () => {
    let resolveMedia!: (stream: MediaStream) => void;
    const track = { stop: vi.fn() };
    const stream = { getTracks: () => [track] } as unknown as MediaStream;
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn(() => new Promise<MediaStream>((resolve) => { resolveMedia = resolve; })) },
    });
    const handlers = callbacks();
    const runtime = await createBrowserVoiceRuntime({
      state: "ready", token: "ephemeral", wsUrl: "ws://offline.test/ws/audio", ttlSec: 120, mode: "mock",
    }, handlers);

    const starting = runtime.start();
    runtime.stop();
    resolveMedia(stream);

    await expect(starting).rejects.toMatchObject({ name: "AbortError" });
    expect(track.stop).toHaveBeenCalledTimes(1);
    expect(handlers.onConnection).toHaveBeenLastCalledWith("disconnected");
  });

  it("stops the acquired microphone when audio context startup fails", async () => {
    const track = { stop: vi.fn() };
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn(async () => ({ getTracks: () => [track] } as unknown as MediaStream)) },
    });
    FakeAudioContext.resumeError = new Error("resume rejected");
    const runtime = await createBrowserVoiceRuntime({
      state: "ready", token: "ephemeral", wsUrl: "ws://offline.test/ws/audio", ttlSec: 120, mode: "mock",
    }, callbacks());

    await expect(runtime.start()).rejects.toThrow("resume rejected");
    runtime.stop();

    expect(track.stop).toHaveBeenCalledTimes(1);
    expect(FakeAudioContext.instances[0]?.close).toHaveBeenCalledTimes(1);
  });

  it("does not send microphone frames until the worker mode is validated", async () => {
    const track = { stop: vi.fn() };
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn(async () => ({ getTracks: () => [track] } as unknown as MediaStream)) },
    });
    const runtime = await createBrowserVoiceRuntime({
      state: "ready", token: "ephemeral", wsUrl: "ws://offline.test/ws/audio", ttlSec: 120, mode: "mock",
    }, callbacks());

    const starting = runtime.start();
    await vi.waitFor(() => expect(sdk.instances[0]?.connect).toHaveBeenCalledTimes(1));
    const context = FakeAudioContext.instances[0];
    const client = sdk.instances[0];
    const audioEvent = { inputBuffer: { getChannelData: () => new Float32Array([0.2, -0.2]) } };
    context?.processor.onaudioprocess?.(audioEvent);
    expect(client?.sendAudioChunk).not.toHaveBeenCalled();

    if (client) readyMetric(client);
    await starting;
    context?.processor.onaudioprocess?.(audioEvent);
    expect(client?.sendAudioChunk).toHaveBeenCalledTimes(1);

    runtime.stop();
  });
});
