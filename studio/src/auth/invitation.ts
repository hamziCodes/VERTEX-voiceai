import "server-only";

import { createHmac, timingSafeEqual } from "node:crypto";

export const INVITATION_COOKIE_NAME = "wavia-pending-invitation";
const MAX_AGE_SECONDS = 60 * 30;

function isInvitationToken(value: string): boolean {
  return value.length >= 20 && value.length <= 1024 && /^[A-Za-z0-9_-]+$/.test(value);
}

export function sealInvitationToken(token: string, secret: string): string {
  if (!isInvitationToken(token)) throw new Error("Invalid invitation token.");
  const payload = Buffer.from(token, "utf8").toString("base64url");
  const mac = createHmac("sha256", secret).update(`wavia:invitation:${payload}`).digest("base64url");
  return `v1.${payload}.${mac}`;
}

export function unsealInvitationToken(value: string, secret: string): string | null {
  const [version, payload, mac, extra] = value.split(".");
  if (version !== "v1" || !payload || !mac || extra) return null;
  const expected = createHmac("sha256", secret).update(`wavia:invitation:${payload}`).digest();
  const supplied = Buffer.from(mac, "base64url");
  if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) return null;
  const token = Buffer.from(payload, "base64url").toString("utf8");
  return isInvitationToken(token) ? token : null;
}

export function invitationCookieOptions(secure = process.env.NODE_ENV === "production") {
  return { httpOnly: true as const, sameSite: "lax" as const, secure, path: "/" as const, maxAge: MAX_AGE_SECONDS };
}
