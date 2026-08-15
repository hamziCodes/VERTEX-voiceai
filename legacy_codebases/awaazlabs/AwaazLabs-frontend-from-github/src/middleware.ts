import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';
import { NextResponse } from 'next/server';

import { DEBUG_BYPASS_AUTH } from '@/shared/debug-auth';
import { SELECT_ORG_PATH, isAllowedOrg } from '@/shared/org-access';

/**
 * AUTHENTICATION AND ORGANIZATION BOUNDARY.
 *
 * This is the only thing standing between an anonymous request and a dashboard that renders
 * patient-level data. Everything downstream — `RouteGuard`, the nav's `visibleWhen`
 * predicates, the field omission in `data-access.ts` — assumes a request got past here.
 *
 * Two gates, in order:
 *   1. Authenticated?                      -> else redirect to /sign-in
 *   2. Active org is the allowed one?      -> else redirect to /select-organization
 *
 * A note on why middleware is acceptable here, having previously been avoided:
 * `next.config.mjs` used to record that this app deliberately shipped no middleware, citing
 * CVE-2025-29927 (the `x-middleware-subrequest` auth bypass). That CVE was patched in
 * Next.js 15.2.3 and this app runs 15.5.20 — verified against the installed package, not
 * assumed. The bypass is closed.
 */

/**
 * Public. No session required.
 *
 * `/sign-in(.*)` covers Clerk's sub-paths (second factor, SSO callback, password reset).
 * Omitting the wildcard would let a user authenticate and then be bounced on the MFA step.
 *
 * There is deliberately no `/sign-up`: §16.3 specifies members are added by "invite by email
 * with role assignment (Owner only)". Sign-up is disabled in the Clerk dashboard too — this
 * matcher alone would not stop someone reaching Clerk's hosted page.
 */
const isPublicRoute = createRouteMatcher(['/sign-in(.*)']);

/**
 * Requires a session, but not an active organization — otherwise the page that *fixes* a
 * missing organization would redirect to itself forever.
 */
const isOrgExemptRoute = createRouteMatcher([`${SELECT_ORG_PATH}(.*)`]);

export default clerkMiddleware(async (auth, request) => {
  // DEBUG: skip Clerk sign-in, org selection, and email/MFA verification.
  if (DEBUG_BYPASS_AUTH) {
    const path = request.nextUrl.pathname;
    if (path.startsWith('/sign-in') || path.startsWith(SELECT_ORG_PATH)) {
      return NextResponse.redirect(new URL('/', request.url));
    }
    return;
  }

  if (isPublicRoute(request)) return;

  const { userId, orgId, orgSlug, redirectToSignIn } = await auth();

  /**
   * Gate 1 — authentication.
   *
   * Bare `auth.protect()` responds 404 to an anonymous request. Defensible — it does not
   * confirm the route exists — but it strands a signed-out user on a dead page. Redirect
   * explicitly, preserving the deep link so `/vob-queue?filter=needs-attention` survives the
   * round trip through login.
   *
   * The target comes from `NEXT_PUBLIC_CLERK_SIGN_IN_URL`. Without it Clerk sends users to
   * its hosted Account Portal on a different domain — not the page we built.
   */
  if (!userId) return redirectToSignIn({ returnBackUrl: request.url });

  if (isOrgExemptRoute(request)) return;

  /**
   * Gate 2 — organization membership.
   *
   * `orgId` / `orgSlug` are populated only when the session has an *active* organization. A
   * member who has simply never selected one arrives with both `null`, which is not a denial
   * — `/select-organization` activates it for them silently. A genuine non-member reaches the
   * same page and is told, plainly, that they need an invitation.
   *
   * Matching prefers the organization **slug**, which is stable across Clerk's development
   * and production instances (each mints a different organization id for the same org). The
   * id is checked as a fallback, because slugs are an optional Clerk feature: on an instance
   * with them disabled, `orgSlug` can be `null` for a legitimate member and a slug-only check
   * would lock the whole organization out. Either identifier matching grants access.
   */
  if (!isAllowedOrg(orgId, orgSlug)) {
    const url = new URL(SELECT_ORG_PATH, request.url);
    url.searchParams.set('redirect_url', request.url);
    return NextResponse.redirect(url);
  }
});

export const config = {
  matcher: [
    /**
     * Everything except Next internals and static files — unless the request carries search
     * params, which is how a deep link like `/vob-queue?filter=needs-attention` arrives.
     * Skipping those would let an unauthenticated user reach a protected page by appending a
     * query string.
     */
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    // Always run for API routes.
    '/(api|trpc)(.*)',
  ],
};
