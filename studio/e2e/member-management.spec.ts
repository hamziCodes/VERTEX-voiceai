import { createHmac } from "node:crypto";
import path from "node:path";

import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { sealData } from "iron-session";

const cookiePassword = `test-${"x".repeat(32)}`;
const fixtureBaseUrl = `http://127.0.0.1:${process.env.WAVIA_E2E_FIXTURE_PORT ?? "3211"}`;
const captureDirectory = path.resolve(process.cwd(), "../hamza_local/phase13h-qa");
// Labelled offline fixture value seeded by e2e/fixtures/offline-auth-server.mjs.
const expiredInvitationToken = "offline_expired_invitation_token_0001";

async function authenticate(context: BrowserContext, subject: string) {
  const tokenResponse = await fetch(`${fixtureBaseUrl}/token?sub=${subject}`, { headers: { connection: "close" } });
  const { accessToken } = await tokenResponse.json() as { accessToken: string };
  const value = await sealData({
    accessToken,
    refreshToken: "offline-refresh-token",
    user: { id: subject, email: `${subject}@example.test`, firstName: "Offline", lastName: "User" },
  }, { password: cookiePassword, ttl: 0 });
  await context.addCookies([{ name: "wos-session", value, domain: "127.0.0.1", path: "/", httpOnly: true, sameSite: "Lax" }]);
}

// Mirrors studio/src/auth/invitation.ts so a replayed or expired token can be presented again.
async function holdPendingInvitation(context: BrowserContext, token: string) {
  const payload = Buffer.from(token, "utf8").toString("base64url");
  const mac = createHmac("sha256", cookiePassword).update(`wavia:invitation:${payload}`).digest("base64url");
  await context.addCookies([{ name: "wavia-pending-invitation", value: `v1.${payload}.${mac}`, domain: "127.0.0.1", path: "/", httpOnly: true, sameSite: "Lax" }]);
}

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  return errors;
}

async function openMembers(page: Page) {
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await page.getByRole("link", { name: /Members/ }).click();
  await expect(page).toHaveURL(/\/settings\/members$/);
  await expect(page.getByRole("heading", { name: "Members", exact: true })).toBeVisible();
}

async function createInvitation(page: Page, email: string, roleName: RegExp): Promise<string> {
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("radio", { name: roleName }).check();
  await page.getByRole("button", { name: "Create invitation" }).click();
  const reveal = page.getByRole("region", { name: `Invitation link for ${email}` });
  await expect(reveal).toBeVisible();
  const link = await reveal.getByLabel("Invitation link").inputValue();
  const token = new URL(link).searchParams.get("invitation");
  expect(token).toBeTruthy();
  return link;
}

test.beforeEach(async () => {
  await fetch(`${fixtureBaseUrl}/reset`, { method: "POST", headers: { connection: "close" } });
});

test("administrator invites, changes roles and removes members with last-admin protection", async ({ context, page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await authenticate(context, "user-two");
  await openMembers(page);

  const list = page.getByRole("list", { name: "Workspace members" });
  await expect(list.getByRole("listitem")).toHaveCount(5);
  const self = list.getByRole("listitem", { name: /^You/ });
  await expect(self.getByRole("combobox", { name: /Role for/ })).toBeDisabled();
  await expect(self.getByText("Last administrator. Promote another member before changing or removing this role.")).toBeVisible();

  await page.getByRole("radio", { name: /^Administrator/ }).check();
  await expect(page.getByRole("form", { name: "Invite a member" }).getByRole("note")).toContainText("Administrators can invite and remove members");
  const link = await createInvitation(page, "user-new@example.test", /^Editor/);
  const token = new URL(link).searchParams.get("invitation") as string;
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  await expect(list).not.toContainText(token);
  if (process.env.CAPTURE_PHASE13H === "1") {
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-members-reveal-desktop-20261112.png"), fullPage: true });
  }
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.getByRole("region", { name: /Invitation link/ })).toHaveCount(0);
  expect(await page.content()).not.toContain(token);

  const editorRow = list.getByRole("listitem", { name: /bbbbbbbb/ });
  await editorRow.getByRole("combobox", { name: /Role for/ }).selectOption("tenant_admin");
  await expect(editorRow.getByRole("note")).toContainText("Administrators can invite and remove members");
  await editorRow.getByRole("button", { name: /Update role/ }).click();
  await expect(page.getByRole("status").filter({ hasText: "Role updated" })).toContainText("Role updated to Administrator.");
  await expect(self.getByRole("combobox", { name: /Role for/ })).toBeEnabled();

  const viewerRow = list.getByRole("listitem", { name: /cccccccc/ });
  await viewerRow.getByRole("button", { name: /Remove/ }).click();
  const dialog = page.getByRole("dialog", { name: "Remove member" });
  await expect(dialog).toContainText("They lose access to Alpha workspace immediately.");
  await dialog.getByRole("button", { name: "Remove member" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Member removed" })).toBeVisible();
  await expect(list.getByRole("listitem", { name: /cccccccc/ })).toHaveCount(0);

  if (process.env.CAPTURE_PHASE13H === "1") {
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-members-desktop-20261112.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await page.screenshot({ path: path.join(captureDirectory, "phase13h-members-mobile-390-20261112.png"), fullPage: true });
  }
  expect(consoleErrors).toEqual([]);
});

test("editors see a read-only member list and cannot mutate through the server", async ({ context, page }) => {
  await authenticate(context, "user-editor");
  await openMembers(page);

  await expect(page.getByText("Your role can view members but cannot invite, change roles, or remove members.")).toBeVisible();
  await expect(page.getByRole("form", { name: "Invite a member" })).toHaveCount(0);
  await expect(page.getByRole("combobox")).toHaveCount(0);
  await expect(page.getByRole("list", { name: "Workspace members" }).getByRole("listitem", { name: /^You/ })).toContainText("Editor");

  // Forged mutation straight to the control plane with the editor's own token is refused there too.
  const tokenResponse = await fetch(`${fixtureBaseUrl}/token?sub=user-editor`, { headers: { connection: "close" } });
  const { accessToken } = await tokenResponse.json() as { accessToken: string };
  const forged = await fetch(`${fixtureBaseUrl}/v1/organizations/11111111-1111-4111-8111-111111111111/invitations`, {
    method: "POST",
    headers: { authorization: `Bearer ${accessToken}`, "x-tenant-id": "11111111-1111-4111-8111-111111111111", "content-type": "application/json", connection: "close" },
    body: JSON.stringify({ email: "intruder@example.test", role: "tenant_admin" }),
  });
  expect(forged.status).toBe(403);
});

test("developers do not see workspace member management", async ({ context, page }) => {
  await authenticate(context, "user-developer");
  await page.goto("/workspaces");
  await page.getByRole("button", { name: /Alpha workspace/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("link", { name: "Settings", exact: true })).toHaveCount(0);
  await page.goto("/settings/members");
  await expect(page).toHaveURL(/\/workspaces\?error=forbidden$/);
});

test("an invitation link works once and replayed or expired links are explained", async ({ browser, context, page }) => {
  await authenticate(context, "user-two");
  await openMembers(page);
  const link = await createInvitation(page, "user-new@example.test", /^Editor/);
  const token = new URL(link).searchParams.get("invitation") as string;
  await page.getByRole("button", { name: "Done" }).click();

  const inviteeContext = await browser.newContext();
  const invitee = await inviteeContext.newPage();
  const consoleErrors = collectConsoleErrors(invitee);
  const appOrigin = new URL(link).origin;
  await invitee.goto(link);
  await expect(invitee.getByText("Your workspace invitation will be ready after sign-in.")).toBeVisible();
  await expect(invitee.locator("body")).not.toContainText(token);
  await holdPendingInvitation(inviteeContext, token);
  await authenticate(inviteeContext, "user-new");
  await invitee.goto(`${appOrigin}/workspaces`);
  await expect(invitee.getByRole("button", { name: /Alpha workspace/ })).toHaveCount(0);
  await invitee.getByRole("button", { name: "Accept invitation" }).click();
  await expect(invitee).toHaveURL(/\/dashboard$/);

  await holdPendingInvitation(inviteeContext, token);
  await invitee.goto(`${appOrigin}/workspaces`);
  await invitee.getByRole("button", { name: "Accept invitation" }).click();
  await expect(invitee).toHaveURL(/\/workspaces\?error=invitation-used$/);
  await expect(invitee.getByRole("alert").and(invitee.locator(".inline-notice"))).toContainText("This invitation has already been used.");
  await expect(invitee.getByRole("button", { name: "Accept invitation" })).toHaveCount(0);

  await holdPendingInvitation(inviteeContext, expiredInvitationToken);
  await invitee.goto(`${appOrigin}/workspaces`);
  await invitee.getByRole("button", { name: "Accept invitation" }).click();
  await expect(invitee).toHaveURL(/\/workspaces\?error=invitation-expired$/);
  await expect(invitee.getByRole("alert").and(invitee.locator(".inline-notice"))).toContainText("This invitation has expired.");
  expect(consoleErrors).toEqual([]);

  await page.reload();
  await expect(page.getByRole("list", { name: "Workspace members" }).getByRole("listitem", { name: /ffffffff/ })).toContainText("Editor");
  await inviteeContext.close();
});
