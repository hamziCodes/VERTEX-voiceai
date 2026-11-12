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

  for (const path of ["/admin/staff", "/admin/audit"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/admin\?error=forbidden$/);
    await expect(page.getByRole("alert").filter({ hasText: "Your platform role cannot open that area." })).toBeVisible();
  }
  expect(consoleErrors).toEqual([]);
});

test("platform admin grants, changes and revokes staff roles with reasons and sees them audited", async ({ context, page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await authenticate(context, "user-platform-admin");
  await page.goto("/admin/staff");
  await expect(page.getByRole("heading", { level: 1, name: "Staff" })).toBeVisible();
  const table = page.getByRole("table", { name: "Platform staff" });
  await expect(table.getByRole("row")).toHaveCount(3);

  // The only administrator is protected in the interface.
  const self = table.getByRole("row", { name: /user-platform-admin@example\.test/ });
  await expect(self.getByRole("button", { name: /Revoke/ })).toBeDisabled();
  await expect(self.getByText("Last platform administrator.")).toBeVisible();

  // A person who never signed in cannot be granted a role.
  await page.getByRole("button", { name: "Grant a role" }).click();
  const grant = page.getByRole("dialog", { name: "Grant a platform role" });
  await expect(grant.getByLabel("Email address")).toBeFocused();
  await grant.getByLabel("Email address").fill("nobody@example.test");
  await grant.getByLabel("Reason").fill("Support rota for Q4 onboarding");
  await grant.getByRole("button", { name: "Grant role" }).click();
  await expect(grant.getByRole("alert")).toContainText("must sign in once");

  await grant.getByLabel("Email address").fill("user-editor@example.test");
  await grant.getByRole("button", { name: "Grant role" }).click();
  await expect(grant).toBeHidden();
  await expect(page.getByRole("status")).toContainText("user-editor@example.test now has Platform support.");

  const editorRow = table.getByRole("row", { name: /user-editor@example\.test/ });
  await editorRow.getByRole("button", { name: /Change role/ }).click();
  const change = page.getByRole("dialog", { name: "Change platform role" });
  await change.getByLabel("Platform role").selectOption("platform_admin");
  await change.getByLabel("Reason").fill("Promoted to platform administration");
  await change.getByRole("button", { name: "Change role" }).click();
  await expect(change).toBeHidden();
  await expect(editorRow).toContainText("Platform administrator");

  await table.getByRole("row", { name: /user-platform-support@example\.test/ }).getByRole("button", { name: /Revoke/ }).click();
  const revoke = page.getByRole("dialog", { name: "Revoke platform role" });
  await expect(revoke.getByRole("button", { name: "Cancel" })).toBeFocused();
  await revoke.getByRole("button", { name: "Revoke role" }).click();
  await expect(revoke.getByRole("alert")).toContainText("Give a reason of at least 8 characters.");
  await revoke.getByLabel("Reason").fill("Left the support rota");
  await revoke.getByRole("button", { name: "Revoke role" }).click();
  await expect(revoke).toBeHidden();
  await expect(table.getByRole("row", { name: /user-platform-support@example\.test/ })).toHaveCount(0);

  await page.goto(`/admin/tenants/${ALPHA}`);
  await expect(page.getByRole("heading", { level: 1, name: "Alpha workspace" })).toBeVisible();
  await page.getByRole("navigation", { name: "Wavia admin" }).getByRole("link", { name: "Audit" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Platform audit" })).toBeVisible();
  const audit = page.getByRole("table", { name: "Platform audit events" });
  await expect(audit.getByRole("row")).toHaveCount(5);
  await expect(audit.getByRole("row").nth(1)).toContainText("Tenant summary viewed");
  await expect(audit).toContainText("Staff role revoked");
  await expect(audit).toContainText("Left the support rota");
  await expect(audit).toContainText("Platform support → Platform administrator");
  await expect(audit).toContainText("Staff role granted");
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBeLessThanOrEqual(1);
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

test("platform support runs a read-only, audited, expiring support session", async ({ browser, context, page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await authenticate(context, "user-platform-support");
  await page.goto("/admin/tenants?q=beta");
  await page.getByRole("table", { name: "Tenant directory" }).getByRole("link", { name: "Beta workspace" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Beta workspace" })).toBeVisible();

  await page.getByRole("button", { name: "Start support session" }).click();
  const dialog = page.getByRole("dialog", { name: "Start a support session" });
  await expect(dialog.getByLabel("Reason")).toBeFocused();
  await dialog.getByLabel("Reason").fill("Customer ticket about agent setup");
  await dialog.getByRole("checkbox", { name: /Readiness/ }).check();
  await dialog.getByLabel("Ticket reference (optional)").fill("TICKET-1042");
  await dialog.getByLabel("Duration").selectOption("15");
  await dialog.getByRole("button", { name: "Start session" }).click();

  await expect(page).toHaveURL(/\/admin\/support-sessions\/[0-9a-f-]+$/);
  const banner = page.getByRole("region", { name: "Support session" });
  await expect(banner).toContainText("Read-only");
  await expect(banner).toContainText("Beta workspace");
  await expect(page.getByRole("table", { name: "Agents" })).toContainText("Viewer-safe assistant");
  await expect(page.getByRole("heading", { name: "Readiness" })).toBeVisible();
  await expect(page.locator("body")).not.toContainText("Help customers clearly.");

  // A second session for the same tenant is refused while the first is active.
  await page.goto("/admin/tenants/22222222-2222-4222-8222-222222222222");
  await page.getByRole("button", { name: "Start support session" }).click();
  const again = page.getByRole("dialog", { name: "Start a support session" });
  await again.getByLabel("Reason").fill("Second attempt for the same ticket");
  await again.getByRole("button", { name: "Start session" }).click();
  await expect(again.getByRole("alert")).toContainText("already have an active support session");
  await again.getByRole("button", { name: "Cancel" }).click();

  await page.goto("/admin/support-sessions");
  const active = page.getByRole("table", { name: "Active support sessions" });
  await expect(active.getByRole("row")).toHaveCount(2);
  await active.getByRole("button", { name: "End support session for Beta workspace" }).click();
  const end = page.getByRole("dialog", { name: "End support session" });
  await end.getByRole("button", { name: "End session" }).click();
  await expect(page.getByRole("heading", { name: "No active support sessions" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Recent support sessions" })).toContainText("Ended");

  // Expiry: start a new one, then let the fixture close its window.
  await page.goto("/admin/tenants/11111111-1111-4111-8111-111111111111");
  await page.getByRole("button", { name: "Start support session" }).click();
  const expiring = page.getByRole("dialog", { name: "Start a support session" });
  await expiring.getByLabel("Reason").fill("Checking setup progress for ticket");
  await expiring.getByRole("button", { name: "Start session" }).click();
  await expect(page.getByRole("region", { name: "Support session" })).toBeVisible();
  await fetch(`${fixtureBaseUrl}/expire-support-sessions`, { method: "POST", headers: { connection: "close" } });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Support session expired" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Agents" })).toHaveCount(0);
  expect(consoleErrors).toEqual([]);

  // The administrator sees every start, view and end in the platform audit.
  const adminContext = await browser.newContext();
  await authenticate(adminContext, "user-platform-admin");
  const adminPage = await adminContext.newPage();
  await adminPage.goto("/admin/audit");
  const audit = adminPage.getByRole("table", { name: "Platform audit events" });
  await expect(audit).toContainText("Support session started");
  await expect(audit).toContainText("Support data viewed");
  await expect(audit).toContainText("Scope: configuration");
  await expect(audit).toContainText("Scope: readiness");
  await expect(audit).toContainText("Support session ended");
  await adminContext.close();
});
