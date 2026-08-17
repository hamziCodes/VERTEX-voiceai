/**
 * DEBUG / LOCAL TESTING ONLY.
 *
 * When `true`, Clerk sign-in, email verification, MFA, and organization selection are
 * skipped — requests go straight to the dashboard with a mock Owner session.
 *
 * Set back to `false` (or delete this file's usage) before any real deployment.
 */
export const DEBUG_BYPASS_AUTH = false;

export const DEBUG_ACTOR = 'debug@localhost';
export const DEBUG_ROLE = 'OWNER_ADMIN' as const;
