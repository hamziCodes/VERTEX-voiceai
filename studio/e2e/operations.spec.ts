import { expect, test, type BrowserContext } from "@playwright/test";
import { sealData } from "iron-session";

const cookiePassword = `test-${"x".repeat(32)}`;
const alphaCallId = "91111111-1111-4111-8111-111111111111";

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

test("reviews tenant-scoped conversations, intelligence, usage, and audit evidence", async ({ page }) => {
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await page.getByRole("link", { name: "Operate" }).click();

  await expect(page.getByRole("heading", { name: "Conversation history" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "completed" })).toBeVisible();
  await page.getByRole("link", { name: "View details" }).first().click();
  await expect(page).toHaveURL(`/conversations/${alphaCallId}`);
  await expect(page.getByText("I need help with an order")).toBeVisible();
  await expect(page.getByText(/Review required/i)).toBeVisible();
  await expect(page.getByText(/Recording available; access is gated/i)).toBeVisible();
  if (process.env.CAPTURE_PHASE13F === "1") {
    await page.screenshot({ path: "test-results/phase13f-conversation-20261105.png", fullPage: true });
  }

  await page.getByRole("link", { name: "Usage" }).click();
  await expect(page.getByRole("heading", { name: "Usage and limits" })).toBeVisible();
  await expect(page.getByText(/Exact period start and end dates are not supplied/i)).toBeVisible();

  await page.getByRole("link", { name: "Audit" }).click();
  await expect(page.getByRole("heading", { name: "Audit history" })).toBeVisible();
  await expect(page.getByText("provider.degraded")).toBeVisible();
});

test("keeps viewer operations tenant-scoped and denies audit", async ({ page }) => {
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Beta workspace/ }).click();
  await page.getByRole("link", { name: "Operate" }).click();

  await expect(page.getByText(/No conversations have been recorded for this workspace/i)).toBeVisible();
  await expect(page.getByRole("link", { name: "Usage" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Audit" })).not.toBeVisible();

  await page.goto(`/conversations/${alphaCallId}`);
  await expect.poll(() => new URL(page.url()).pathname).toBe("/conversations");

  await page.goto("/settings/audit");
  await expect.poll(() => new URL(page.url()).pathname).toBe("/workspaces");
});
