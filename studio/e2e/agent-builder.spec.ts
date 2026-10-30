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

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ context }) => {
  await fetch("http://127.0.0.1:3211/reset", { method: "POST", headers: { connection: "close" } });
  await authenticate(context);
});

test("resumes onboarding and completes the guided agent lifecycle", async ({ page }) => {
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await page.getByRole("link", { name: "Setup" }).click();

  await expect(page.getByLabel("Business name")).toHaveValue("Hamzi Stores");
  await expect(page.getByText("Operating region is required.")).toBeVisible();
  await page.getByLabel("Operating region").fill("Pakistan");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByText("Onboarding saved.")).toBeVisible();

  await page.getByRole("link", { name: "Build" }).click();
  await page.getByRole("link", { name: "Create agent" }).click();
  await page.getByLabel(/Retail customer care/).check();
  await page.getByLabel("Agent name").fill("Store assistant");
  await page.getByRole("button", { name: "Create agent" }).click();
  await page.getByRole("link", { name: "Continue building" }).click();

  await page.getByLabel("Description").fill("Handles order and return questions");
  await expect(page.getByText(/Saved at revision 2/)).toBeVisible();
  await page.getByRole("button", { name: "Check readiness" }).click();
  await expect(page.getByText("Ready to publish.")).toBeVisible();
  await page.getByRole("button", { name: "Publish agent" }).click();
  await expect(page.getByText("Published version 1.")).toBeVisible();

  await page.reload();
  if (process.env.CAPTURE_PHASE13C === "1") {
    await page.screenshot({ path: "test-results/phase13c-agent-builder.png", fullPage: true });
  }
  await page.getByRole("button", { name: "Restore version 1" }).click();
  await expect(page.getByText("Version 1 remains immutable; its snapshot was copied into a new draft.")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/33333333-3333-4333-8333-/);
});

test("keeps viewer workspaces read-only without exposing internal identifiers", async ({ page }) => {
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Beta workspace/ }).click();
  await page.getByRole("link", { name: "Build" }).click();
  await page.getByRole("link", { name: "View agent" }).click();

  await expect(page.getByText("You have view-only access.")).toBeVisible();
  await expect(page.getByLabel("Agent name")).toBeDisabled();
  await page.getByRole("button", { name: "Advanced" }).click();
  await expect(page.getByLabel("System prompt")).toBeDisabled();
  await expect(page.locator("body")).not.toContainText("44444444-4444-4444-8444-444444444444");
});
