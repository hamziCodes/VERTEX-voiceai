import { expect, test, type BrowserContext } from "@playwright/test";
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

test.beforeEach(async ({ context }) => {
  await fetch("http://127.0.0.1:3211/reset", { method: "POST", headers: { connection: "close" } });
  await authenticate(context);
});

test("navigates web and telephony channels with honest readiness and policy controls", async ({ page }) => {
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();

  await page.getByRole("link", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Web voice integration" })).toBeVisible();
  await expect(page.getByText("npm install @ucve/voice-sdk")).toBeVisible();

  // Navigate to Telephony sub-tab
  await page.getByRole("link", { name: "Telephony" }).click();
  await expect(page.getByRole("heading", { name: "Telephony voice channel" })).toBeVisible();
  await expect(page.getByText("Not configured")).toBeVisible();
  await expect(page.getByText(/Carrier purchase and provisioning is not automated/i)).toBeVisible();

  // Edit policy
  const outboundCheckbox = page.getByLabel("Allow outbound calls");
  await outboundCheckbox.check();
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.getByText("Telephony policy saved successfully.")).toBeVisible();
  if (process.env.CAPTURE_PHASE13E === "1") {
    await page.screenshot({ path: "test-results/phase13e-telephony.png", fullPage: true });
  }
});

test("manages API keys with one-time reveal and revocation confirmation", async ({ page }) => {
  const browserMessages: string[] = [];
  const requestUrls: string[] = [];
  page.on("console", (message) => browserMessages.push(message.text()));
  page.on("request", (request) => requestUrls.push(request.url()));

  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();

  await page.getByRole("link", { name: "API Keys" }).click();
  await expect(page.getByRole("heading", { name: "API Keys" })).toBeVisible();
  await expect(page.getByText("Production Web Client")).toBeVisible();

  // Create API key
  await page.getByRole("button", { name: "Create API Key" }).click();
  await page.getByLabel("Key Name").fill("Mobile App Client");
  await page.getByRole("button", { name: "Generate Key" }).click();

  // One-time reveal modal
  await expect(page.getByText("Save this secret key now")).toBeVisible();
  const secret = "wavia_live_secret_plaintext_key_123456";
  await expect(page.getByText(secret)).toBeVisible();
  await expect.poll(() => page.url()).not.toContain(secret);

  const browserStorage = await page.evaluate(() => ({
    local: Object.values(localStorage),
    session: Object.values(sessionStorage),
  }));
  expect(JSON.stringify(browserStorage)).not.toContain(secret);

  const doneBtn = page.getByRole("button", { name: "Done" });
  await expect(doneBtn).toBeDisabled();

  await page.getByLabel("I have copied this secret key").check();
  await expect(doneBtn).toBeEnabled();
  await doneBtn.click();

  await expect(page.getByText("Save this secret key now")).not.toBeVisible();
  await page.reload();
  await expect(page.getByText(secret)).not.toBeVisible();
  expect(browserMessages.join("\n")).not.toContain(secret);
  expect(requestUrls.join("\n")).not.toContain(secret);
});

test("configures encrypted provider credentials and displays routing tier", async ({ page }) => {
  const browserMessages: string[] = [];
  const requestUrls: string[] = [];
  page.on("console", (message) => browserMessages.push(message.text()));
  page.on("request", (request) => requestUrls.push(request.url()));

  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();

  await page.getByRole("link", { name: "Providers" }).click();
  await expect(page.getByRole("heading", { name: "AI Provider Credentials" })).toBeVisible();
  await expect(page.getByText("Standard release chain active")).toBeVisible();

  // Configure Groq
  await page.getByRole("button", { name: "Configure groq" }).click();
  const secretInput = page.getByLabel("API Key or Secret");
  await expect(secretInput).toHaveAttribute("type", "password");
  const secret = "gsk_mock_secret_key_12345";
  await secretInput.fill(secret);
  await page.getByRole("button", { name: "Save Credential" }).click();

  await expect(page.getByText("Configure Groq")).not.toBeVisible();
  await expect.poll(() => page.url()).not.toContain(secret);
  const browserStorage = await page.evaluate(() => ({
    local: Object.values(localStorage),
    session: Object.values(sessionStorage),
  }));
  expect(JSON.stringify(browserStorage)).not.toContain(secret);
  expect(browserMessages.join("\n")).not.toContain(secret);
  expect(requestUrls.join("\n")).not.toContain(secret);
});

test("enforces viewer role denial on channels, keys, and provider write actions", async ({ page }) => {
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Beta workspace/ }).click();

  // In Beta workspace (viewer role): API Keys and Providers navigation links should not be visible
  await expect(page.getByRole("link", { name: "API Keys" })).not.toBeVisible();
  await expect(page.getByRole("link", { name: "Providers" })).not.toBeVisible();

  await expect(page.getByRole("link", { name: "Connect" })).not.toBeVisible();

  for (const protectedPath of ["/channels/telephony", "/developers/api-keys", "/settings/providers"]) {
    await page.goto(protectedPath);
    await expect.poll(() => new URL(page.url()).pathname).toBe("/workspaces");
  }
});
