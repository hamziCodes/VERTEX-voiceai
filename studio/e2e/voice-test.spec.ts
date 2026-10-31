import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { sealData } from "iron-session";

const cookiePassword = `test-${"x".repeat(32)}`;

async function authenticate(context: BrowserContext) {
  const tokenResponse = await fetch("http://127.0.0.1:3211/token?sub=user-two", { headers: { connection: "close" } });
  const { accessToken } = await tokenResponse.json() as { accessToken: string };
  const value = await sealData({
    accessToken,
    refreshToken: "offline-refresh-token",
    user: { id: "user-two", email: "user-two@example.test", firstName: "Offline", lastName: "User" },
  }, { password: cookiePassword, ttl: 0 });
  await context.addCookies([{ name: "wos-session", value, domain: "127.0.0.1", path: "/", httpOnly: true, sameSite: "Lax" }]);
}

async function installOfflineMedia(page: Page) {
  await page.addInitScript(() => {
    const state = { socketsClosed: 0, tracksStopped: 0, contextsClosed: 0, mediaRequests: 0, sentEvents: [] as Array<{ event_type?: string; payload?: Record<string, unknown> }> };
    Object.defineProperty(window, "__voiceTestState", { value: state });
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: {
      getUserMedia: async () => { state.mediaRequests += 1; return { getTracks: () => [{ stop: () => { state.tracksStopped += 1; } }] }; },
    } });

    class OfflineAudioContext {
      state = "running";
      currentTime = 0;
      destination = {};
      resume = async () => undefined;
      close = async () => { this.state = "closed"; state.contextsClosed += 1; };
      createMediaStreamSource = () => ({ connect() {}, disconnect() {} });
      createScriptProcessor = () => ({ connect() {}, disconnect() {}, onaudioprocess: null });
      createBuffer = (_channels: number, length: number) => {
        const channel = new Float32Array(length);
        return { getChannelData: () => channel };
      };
      createBufferSource = () => ({
        buffer: null,
        onended: null as null | (() => void),
        connect() {},
        start() {},
        stop() { this.onended?.(); },
      });
    }
    Object.defineProperty(window, "AudioContext", { configurable: true, value: OfflineAudioContext });

  });
}

async function installOfflineWorker(page: Page) {
  await page.evaluate(() => {
    const state = (window as unknown as { __voiceTestState: { socketsClosed: number; tracksStopped: number; mediaRequests: number; sentEvents: Array<{ event_type?: string; payload?: Record<string, unknown> }> } }).__voiceTestState;
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: {
      getUserMedia: async () => { state.mediaRequests += 1; return { getTracks: () => [{ stop: () => { state.tracksStopped += 1; } }] }; },
    } });
    class OfflineWebSocket {
      static OPEN = 1;
      readyState = OfflineWebSocket.OPEN;
      binaryType = "arraybuffer";
      onopen: null | (() => void) = null;
      onmessage: null | ((event: { data: string | ArrayBuffer }) => void) = null;
      onerror: null | (() => void) = null;
      onclose: null | ((event: { code: number; reason: string }) => void) = null;
      constructor(public url: string) { queueMicrotask(() => this.onopen?.()); }
      send(value: string | ArrayBuffer | ArrayBufferView) {
        if (typeof value !== "string") return;
        const event = JSON.parse(value) as { event_type?: string };
        state.sentEvents.push(event);
        if (event.event_type !== "protocol.hello") return;
        queueMicrotask(() => this.onmessage?.({ data: JSON.stringify({ event_type: "session.ready", payload: { protocol_version: "1.0.0" } }) }));
        setTimeout(() => {
          this.onmessage?.({ data: JSON.stringify({ event_type: "metric", payload: { kind: "session_ready", provider_mode: "mock", stt_transcript_mode: "fixed_mock" } }) });
          this.onmessage?.({ data: JSON.stringify({ event_type: "transcript.final", payload: { speaker: "user", text: "Where is my order?" } }) });
          this.onmessage?.({ data: JSON.stringify({ event_type: "transcript.final", payload: { speaker: "agent", text: "I can help track it." } }) });
          this.onmessage?.({ data: JSON.stringify({ event_type: "metric.latency", payload: { durations_ms: { stt_after_acoustic_end: 205, llm_ttft: 140, tts_ttfb: 90, user_perceived_e2e: 650 } } }) });
          this.onmessage?.({ data: JSON.stringify({ event_type: "audio.start", payload: { turn_id: "turn-1", server_send_ms: 1 } }) });
          this.onmessage?.({ data: new Int16Array([0, 100, -100]).buffer });
          this.onmessage?.({ data: JSON.stringify({ event_type: "control.clear_audio", payload: { turn_id: "turn-1", sequence: 1, reason: "barge_in" } }) });
          setTimeout(() => this.onclose?.({ code: 1011, reason: "offline worker closed" }), 25);
        }, 10);
      }
      close() { this.readyState = 3; state.socketsClosed += 1; }
    }
    Object.defineProperty(window, "WebSocket", { configurable: true, value: OfflineWebSocket });
  });
}

test.beforeEach(async ({ context, page }) => {
  await fetch("http://127.0.0.1:3211/reset", { method: "POST", headers: { connection: "close" } });
  await authenticate(context);
  await installOfflineMedia(page);
});

test("runs an SDK-backed offline voice test and releases browser media", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await page.getByRole("link", { name: "Build" }).click();
  await page.getByRole("link", { name: "Create agent" }).click();
  await page.getByLabel(/Retail customer care/).check();
  await page.getByLabel("Agent name").fill("Voice test agent");
  await page.getByRole("button", { name: "Create agent" }).click();
  await page.getByRole("link", { name: "Continue building" }).click();
  await page.getByRole("button", { name: "Check readiness" }).click();
  await page.getByRole("button", { name: "Publish agent" }).click();
  await expect(page.getByText("Published version 1.")).toBeVisible();
  await page.getByRole("link", { name: "Build" }).click();
  await page.getByRole("link", { name: "Test voice" }).click();

  await expect(page.getByText("Mock mode")).toBeVisible();
  await installOfflineWorker(page);
  await page.getByRole("button", { name: "Start voice test" }).click();
  await expect.poll(() => page.evaluate(() => (window as unknown as { __voiceTestState: { mediaRequests: number } }).__voiceTestState.mediaRequests)).toBe(1);
  await expect.poll(() => page.evaluate(() => (window as unknown as { __voiceTestState: { sentEvents: unknown[] } }).__voiceTestState.sentEvents.length)).toBeGreaterThan(0);
  await expect(page.getByText("Where is my order?")).toBeVisible();
  await expect(page.getByText("I can help track it.")).toBeVisible();
  await expect(page.getByText("650 ms")).toBeVisible();
  await expect(page.getByText("Playback cleared for interruption.")).toBeVisible();
  await expect(page.getByText("Connection:").locator(".." )).toContainText("disconnected");

  const cleanupState = await page.evaluate(() => (window as unknown as { __voiceTestState: {
    socketsClosed: number;
    tracksStopped: number;
    contextsClosed: number;
    sentEvents: Array<{ event_type?: string; payload?: Record<string, unknown> }>;
  } }).__voiceTestState);
  expect(cleanupState.socketsClosed).toBe(1);
  expect(cleanupState.tracksStopped).toBe(1);
  expect(cleanupState.contextsClosed).toBe(1);
  const clearAck = cleanupState.sentEvents.find((event: { event_type?: string }) => event.event_type === "control.clear_audio_ack");
  expect(clearAck?.payload?.played_audio_ms).toBe(0);
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length, href: location.href }))).toEqual({ local: 0, session: 0, href: expect.not.stringContaining("offline-ephemeral-room-token") });
  expect(consoleErrors).toEqual([]);
  if (process.env.CAPTURE_PHASE13D === "1") await page.screenshot({ path: "test-results/phase13d-voice-test.png", fullPage: true });
});
