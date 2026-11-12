import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { sealData } from "iron-session";

const cookiePassword = `test-${"x".repeat(32)}`;
const fixtureBaseUrl = `http://127.0.0.1:${process.env.WAVIA_E2E_FIXTURE_PORT ?? "3211"}`;
const ALPHA = "11111111-1111-4111-8111-111111111111";

async function authenticate(context: BrowserContext, subject: string) {
  const tokenResponse = await fetch(`${fixtureBaseUrl}/token?sub=${subject}`, { headers: { connection: "close" } });
  const { accessToken } = await tokenResponse.json() as { accessToken: string };
  const value = await sealData({
    accessToken,
    refreshToken: "offline-refresh-token",
    user: { id: subject, email: `${subject}@example.test`, firstName: "Offline", lastName: "Staff" },
  }, { password: cookiePassword, ttl: 0 });
  await context.addCookies([{ name: "wos-session", value, domain: "127.0.0.1", path: "/", httpOnly: true, sameSite: "Lax" }]);
}

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

test.beforeEach(async () => {
  await fetch(`${fixtureBaseUrl}/reset`, { method: "POST", headers: { connection: "close" } });
});

test("customers cannot discover the internal area", async ({ context, page }) => {
  await authenticate(context, "user-two");
  await page.goto("/workspaces");
  await expect(page.getByRole("heading", { name: "Choose a workspace" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Wavia admin/ })).toHaveCount(0);

  for (const path of ["/admin", "/admin/tenants", `/admin/tenants/${ALPHA}`, "/admin/staff", "/admin/audit"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Wavia admin" })).toHaveCount(0);
  }
});

test("platform support searches tenants read-only and cannot open staff or audit", async ({ context, page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await authenticate(context, "user-platform-support");
  await page.goto("/workspaces");
  await page.getByRole("link", { name: "Open Wavia admin" }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByRole("heading", { level: 1, name: "Platform overview" })).toBeVisible();

  const nav = page.getByRole("navigation", { name: "Wavia admin" });
  await expect(nav.getByRole("link", { name: "Tenants" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Staff" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Audit" })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Workspace" })).toHaveCount(0);

  await nav.getByRole("link", { name: "Tenants" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Tenants" })).toBeVisible();
  await page.getByRole("searchbox", { name: "Search tenants" }).fill("alpha");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page).toHaveURL(/\/admin\/tenants\?q=alpha$/);
  const table = page.getByRole("table", { name: "Tenant directory" });
  await expect(table.getByRole("row")).toHaveCount(2);
  await table.getByRole("link", { name: "Alpha workspace" }).click();

  await expect(page.getByRole("heading", { level: 1, name: "Alpha workspace" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Members by role" })).toContainText("Administrator");
  await expect(page.getByText(/recorded in the platform audit/)).toBeVisible();

  await page.goto("/admin/tenants?q=zeta");
  await expect(page.getByRole("heading", { name: "No matching tenants" })).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test("platform admin pages through the bounded tenant directory", async ({ context, page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await authenticate(context, "user-platform-admin");
  await page.goto("/admin/tenants");
  await expect(page.getByText("Showing 1–25 of 28 tenants")).toBeVisible();
  await expect(page.getByRole("table", { name: "Tenant directory" }).getByRole("row")).toHaveCount(26);

  const pages = page.getByRole("navigation", { name: "Tenant directory pages" });
  await pages.getByRole("link", { name: "Next page" }).click();
  await expect(page).toHaveURL(/\/admin\/tenants\?page=2$/);
  await expect(page.getByText("Showing 26–28 of 28 tenants")).toBeVisible();
  await expect(pages.getByRole("link", { name: "Next page" })).toHaveCount(0);
  await pages.getByRole("link", { name: "Previous page" }).click();
  await expect(page).toHaveURL(/\/admin\/tenants\?page=1$/);

  await page.goto(`/admin/tenants/${"9".repeat(8)}-9999-4999-8999-${"9".repeat(12)}`);
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  expect(consoleErrors.filter((message) => !message.includes("404"))).toEqual([]);
});
