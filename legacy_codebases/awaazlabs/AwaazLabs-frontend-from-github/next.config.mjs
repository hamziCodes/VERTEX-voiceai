const isProd = process.env.NODE_ENV === 'production';

/**
 * Clerk's frontend API host.
 *
 * A development instance serves from `https://<slug>.clerk.accounts.dev`. A production
 * instance serves from `https://clerk.<your-domain>`. The publishable key encodes the host,
 * but it is not available to this config at build time in a form worth parsing, so it is
 * declared explicitly.
 *
 * Set `NEXT_PUBLIC_CLERK_FRONTEND_API_URL` in production. The development default is a
 * wildcard over `clerk.accounts.dev` only — never a bare `*`.
 */
const clerkFrontendApi = process.env.NEXT_PUBLIC_CLERK_FRONTEND_API_URL ?? 'https://*.clerk.accounts.dev';

/**
 * Content Security Policy.
 *
 * `'unsafe-inline'` is required for `script-src` because Next.js inlines its hydration
 * bootstrap. Eliminating it needs a per-request nonce; Clerk can generate one via
 * `clerkMiddleware({ contentSecurityPolicy })`, which is the correct next step once this is
 * stable. Documented rather than silently accepted.
 *
 * `'unsafe-eval'` is development-only: React Refresh requires it. It is absent in prod.
 *
 * Every Clerk allowance below is a specific host, never a wildcard scheme:
 *
 *   script-src   Clerk's SDK is loaded from the frontend API host.
 *   connect-src  The browser talks to Clerk's API for session and token refresh.
 *                `clerk-telemetry.com` is Clerk's anonymous telemetry endpoint. It is
 *                deliberately ALLOWED rather than silently blocked by CSP, because a
 *                CSP violation is not consent management. Disable it properly with
 *                `telemetry={{ disabled: true }}` on ClerkProvider if you object.
 *   img-src      Avatars and organisation logos.
 *   worker-src   Clerk uses a blob-backed worker for session refresh.
 *   frame-src    Cloudflare Turnstile, Clerk's bot-protection challenge.
 *
 * Note what did NOT change: `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'`,
 * and `form-action 'self'`. Authentication widened the network surface; it did not weaken
 * clickjacking, plugin, or form-hijacking protection.
 */
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isProd ? '' : " 'unsafe-eval'"} ${clerkFrontendApi} https://challenges.cloudflare.com`,
  "style-src 'self' 'unsafe-inline'",
  'img-src \'self\' data: blob: https://img.clerk.com',
  "font-src 'self' data:",
  `connect-src 'self' ${clerkFrontendApi} https://clerk-telemetry.com`,
  "media-src 'self'",
  "worker-src 'self' blob:",
  'frame-src https://challenges.cloudflare.com',
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  'upgrade-insecure-requests',
].join('; ');

const securityHeaders = [
  { key: 'Content-Security-Policy', value: csp },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  {
    key: 'Permissions-Policy',
    value: 'camera=(), microphone=(), geolocation=(), interest-cohort=()',
  },
  { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
  { key: 'X-DNS-Prefetch-Control', value: 'off' },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Do not advertise the framework version to an attacker enumerating targets.
  poweredByHeader: false,

  // Fail the Vercel build on a type or lint error rather than shipping a broken deploy.
  // Both default to blocking already; stated explicitly so nobody "fixes" a red build by
  // turning them off.
  typescript: { ignoreBuildErrors: false },
  eslint: { ignoreDuringBuilds: false },

  async headers() {
    return [{ source: '/:path*', headers: securityHeaders }];
  },
};

export default nextConfig;
