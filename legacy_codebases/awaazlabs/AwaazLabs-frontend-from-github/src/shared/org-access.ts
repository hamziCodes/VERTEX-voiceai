/**
 * ORGANIZATION ACCESS BOUNDARY.
 *
 * This dashboard is reachable only by members of one Clerk organization. Sign-up is
 * disabled, so every account is created or invited by an administrator — but the Clerk
 * *instance* may host other applications and other users. Membership of this organization is
 * what authorizes access to *this* app.
 *
 * Two independent controls, because neither is sufficient alone:
 *   1. Sign-up is disabled in the Clerk dashboard   -> strangers cannot create an account.
 *   2. This organization check                       -> an account that exists for another
 *                                                       app cannot reach this dashboard.
 */

/**
 * The organization's **slug**. This is the primary check.
 *
 * A slug is stable across Clerk instances: a production instance mints a *different*
 * organization id for the same organization, but the slug carries over. Matching on it means
 * one value works for every deployment.
 *
 * The caveat that makes the fallback below necessary: organization slugs are an optional
 * Clerk feature. On an instance with them **disabled**, the session token's `orgSlug` can be
 * `null` even for a legitimate member — and a slug-only check would lock the entire
 * organization out, owner included. That is not hypothetical; it was the state of this
 * instance an hour ago.
 */
export const ALLOWED_ORG_SLUG = process.env.NEXT_PUBLIC_CLERK_ALLOWED_ORG_SLUG ?? '';

/**
 * The organization's **id**. Fallback check.
 *
 * `orgId` is always present when a session has an active organization, regardless of whether
 * slugs are enabled. It is instance-specific, so it must be set per deployment — but it is
 * the identifier that cannot silently disappear.
 *
 * Configure both. Either one matching grants access.
 */
export const ALLOWED_ORG_ID = process.env.NEXT_PUBLIC_CLERK_ALLOWED_ORG_ID ?? '';

/**
 * True when at least one identifier is configured.
 *
 * When neither is set, **every request is denied**. There is deliberately no default.
 *
 * An earlier version defaulted the slug to `healthcare-clinics`, arguing that a forgotten
 * environment variable should not lock everyone out of a deployment. That trade is wrong for
 * this application: a hardcoded default is a guess, and guessing which organization may read
 * patient data is not a safe failure mode. A locked-out deployment is loud, diagnosable, and
 * fixed in thirty seconds. A deployment that silently admits the wrong organization is not.
 */
export const ORG_ACCESS_CONFIGURED = ALLOWED_ORG_SLUG !== '' || ALLOWED_ORG_ID !== '';

/**
 * Does this session's active organization grant access?
 *
 * Slug first (stable across instances), id as the fallback that survives slugs being turned
 * off. Either matching is sufficient; both are checked because each fails in a different way.
 *
 * `orgId` / `orgSlug` are `null` when the session has no active organization — the common
 * case for a member who has never selected one, and **not** a denial.
 * `/select-organization` distinguishes the two.
 *
 * The empty-string guards matter: without them an unconfigured `ALLOWED_ORG_SLUG` of `''`
 * would match a session whose `orgSlug` is `''`, admitting an unintended organization.
 */
export function isAllowedOrg(orgId: string | null | undefined, orgSlug: string | null | undefined): boolean {
  if (!ORG_ACCESS_CONFIGURED) return false;
  if (ALLOWED_ORG_SLUG !== '' && orgSlug === ALLOWED_ORG_SLUG) return true;
  if (ALLOWED_ORG_ID !== '' && orgId === ALLOWED_ORG_ID) return true;
  return false;
}

/** Does a Clerk organization record (from `useOrganizationList`) match the allowed one? */
export function isAllowedOrgRecord(org: { id: string; slug: string | null }): boolean {
  return isAllowedOrg(org.id, org.slug);
}

/** Where a signed-in user without the right active organization is sent. */
export const SELECT_ORG_PATH = '/select-organization';

/**
 * Sanitise a `redirect_url` before navigating to it.
 *
 * `/select-organization?redirect_url=https://evil.example` would otherwise turn this app into
 * an open redirect: an attacker sends a victim a link on our trusted domain, the victim signs
 * in, and lands on the attacker's page believing it is ours. Phishing kits are built on
 * exactly this.
 *
 * Only same-origin, path-absolute URLs survive. `//evil.example` is rejected too — a
 * protocol-relative URL is not a local path, however much it looks like one.
 */
export function safeRedirectPath(candidate: string | null, origin: string): string {
  if (!candidate) return '/';

  // Reject scheme-relative (`//host`) and anything with a backslash, which some browsers
  // normalise to a forward slash.
  if (candidate.startsWith('//') || candidate.includes('\\')) return '/';

  // A bare path is fine.
  if (candidate.startsWith('/')) return candidate;

  // An absolute URL is fine only if it points back at us.
  try {
    const url = new URL(candidate);
    if (url.origin !== origin) return '/';
    return `${url.pathname}${url.search}${url.hash}` || '/';
  } catch {
    return '/';
  }
}
