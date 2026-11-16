import { handleAuth } from "@workos-inc/authkit-nextjs";

/**
 * Return users to the public origin they signed in from. Without `baseURL`,
 * AuthKit derives the post-sign-in redirect from the request Next.js sees
 * (`localhost`, or an internal host behind a load balancer), so the browser
 * lands on an origin that does not hold the new session cookie and is sent
 * straight back to sign-in (found by the Stage 3 customer-journey checkup).
 */
function publicOrigin(): string | undefined {
  const configured = process.env.NEXT_PUBLIC_WORKOS_REDIRECT_URI?.trim();
  if (!configured) return undefined;
  try {
    return new URL(configured).origin;
  } catch {
    return undefined;
  }
}

export const GET = handleAuth({ returnPathname: "/workspaces", baseURL: publicOrigin() });
