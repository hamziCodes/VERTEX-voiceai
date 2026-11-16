import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

/**
 * Customer-journey checkup against the REAL engine.
 *
 * Prerequisite: `WAVIA_STACK_IDP=1 bash scripts/release/container_stack.sh up`
 * (release images: control plane, worker, jobs, PostgreSQL, Redis, plus the
 * offline identity double at 127.0.0.1:3211 standing in for WorkOS). Studio
 * runs here against http://127.0.0.1:28080; nothing else is mocked, and voice
 * tests use the engine's mock providers (WAVIA_VOICE_TEST_MODE=mock).
 */
const appPort = 3100;
const appBaseUrl = `http://127.0.0.1:${appPort}`;

export default defineConfig({
  testDir: "./e2e-journey",
  workers: 1,
  timeout: 180_000,
  expect: { timeout: 20_000 },
  reporter: [["list"]],
  use: {
    baseURL: appBaseUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    permissions: ["microphone"],
    // A real speech recording as the microphone, so the worker's real VAD
    // detects end of speech (a synthetic beep never does).
    launchOptions: {
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        `--use-file-for-fake-audio-capture=${path.resolve(process.cwd(), "e2e-journey/fixtures/caller-speech.wav")}`,
      ],
    },
  },
  outputDir: "../hamza_local/stage3/journey-results",
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port ${appPort}`,
    url: appBaseUrl,
    reuseExistingServer: true,
    timeout: 180_000,
    env: {
      WORKOS_CLIENT_ID: "client_offline_test",
      WORKOS_COOKIE_PASSWORD: `test-${"x".repeat(32)}`,
      NEXT_PUBLIC_WORKOS_REDIRECT_URI: `${appBaseUrl}/auth/callback`,
      WORKOS_API_HOSTNAME: "127.0.0.1",
      WORKOS_API_HTTPS: "false",
      WORKOS_API_PORT: "3211",
      WORKOS_ISSUER: "http://127.0.0.1:3211/",
      WAVIA_CONTROL_PLANE_URL: "http://127.0.0.1:28080",
      WAVIA_VOICE_TEST_MODE: "mock",
    },
  },
});
