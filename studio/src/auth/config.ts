import "server-only";

type AuthEnvironment = Readonly<Record<string, string | undefined>>;

export interface PublicAuthConfig {
  redirectUri: string;
}

export function validateAuthEnvironment(environment: AuthEnvironment): PublicAuthConfig {
  const required = [
    "WORKOS_CLIENT_ID",
    "WORKOS_COOKIE_PASSWORD",
    "NEXT_PUBLIC_WORKOS_REDIRECT_URI",
  ] as const;
  const missing = required.filter((name) => !environment[name]?.trim());
  if (missing.length > 0) {
    throw new Error(`Missing WorkOS configuration: ${missing.join(", ")}`);
  }
  if ((environment.WORKOS_COOKIE_PASSWORD?.length ?? 0) < 32) {
    throw new Error("WORKOS_COOKIE_PASSWORD must contain at least 32 characters.");
  }
  const redirectUri = new URL(environment.NEXT_PUBLIC_WORKOS_REDIRECT_URI as string);
  if (redirectUri.protocol !== "https:" && redirectUri.hostname !== "localhost" && redirectUri.hostname !== "127.0.0.1") {
    throw new Error("The WorkOS redirect URI must use HTTPS outside localhost.");
  }
  return { redirectUri: redirectUri.toString().replace(/\/$/, "") };
}

export function authConfig(): PublicAuthConfig {
  return validateAuthEnvironment(process.env);
}

export function workspaceCookieSecret(): string {
  validateAuthEnvironment(process.env);
  return process.env.WORKOS_COOKIE_PASSWORD as string;
}
