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

test("creates, verifies, activates, and binds tenant-scoped knowledge", async ({ page }) => {
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await page.getByRole("link", { name: "Build" }).click();
  await page.getByRole("link", { name: "Create agent" }).click();
  await page.getByLabel(/Retail customer care/).check();
  await page.getByLabel("Agent name").fill("Knowledge agent");
  await page.getByRole("button", { name: "Create agent" }).click();

  await page.getByRole("link", { name: "Knowledge" }).click();
  await page.getByLabel("Knowledge base name").fill("Store handbook");
  await page.getByRole("button", { name: "Create knowledge base" }).click();
  await expect(page.getByRole("heading", { name: "Store handbook" })).toBeVisible();

  await page.getByLabel("Choose document").setInputFiles({ name: "refunds.txt", mimeType: "text/plain", buffer: Buffer.from("Refunds are available within 30 days.") });
  await page.getByRole("button", { name: "Upload document" }).click();
  await expect(page.getByText("refunds.txt", { exact: true })).toBeVisible();
  await expect(page.locator("strong", { hasText: "Queued" })).toBeVisible();

  await page.getByLabel("FAQ name").fill("Store hours");
  await page.getByLabel("Question", { exact: true }).fill("When are you open?");
  await page.getByLabel("Answer", { exact: true }).fill("We are open from 9 AM to 6 PM.");
  await page.getByRole("button", { name: "Add FAQ" }).click();
  await expect(page.getByText("Store hours.json", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Activate knowledge" })).toBeDisabled();

  await fetch("http://127.0.0.1:3211/advance-knowledge", { method: "POST", headers: { connection: "close" } });
  await page.reload();
  await expect(page.locator("strong", { hasText: "Ready" })).toHaveCount(2);
  await page.getByLabel("Ask your knowledge").fill("What is the refund policy?");
  await page.getByRole("button", { name: "Preview answer" }).click();
  await expect(page.getByText("Refunds are available within 30 days.")).toBeVisible();
  await expect(page.getByText("Refund policy · line 1")).toBeVisible();

  await page.getByRole("button", { name: "Activate knowledge" }).click();
  await expect(page.getByText("Knowledge revision 1 is active.")).toBeVisible();
  await page.getByRole("button", { name: "Connect to agent" }).click();
  await expect(page.getByText("Connected to Knowledge agent as published agent version 1.")).toBeVisible();
  if (process.env.CAPTURE_PHASE13D === "1") {
    await page.screenshot({ path: "test-results/phase13d-knowledge.png", fullPage: true });
  }

  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Beta workspace/ }).click();
  await page.getByRole("link", { name: "Knowledge" }).click();
  await expect(page.getByText("You have view-only access.")).toBeVisible();
  await expect(page.getByText("Store handbook")).toHaveCount(0);
});
