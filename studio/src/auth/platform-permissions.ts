/** Platform staff capabilities FastAPI can return from `/v1/platform/me` (Phase 13J). */
export const PLATFORM_CAPABILITIES = [
  "platform_tenant:read",
  "platform_staff:read",
  "platform_staff:write",
  "platform_audit:read",
  "platform_support_session:read",
  "platform_support_session:write",
  "platform_support_session:manage",
  "platform_operations:read",
] as const;

export type PlatformCapability = (typeof PLATFORM_CAPABILITIES)[number];

/** Presentation only: FastAPI repeats every platform permission check. Unknown strings never match. */
export function hasPlatformCapability(capabilities: readonly string[], required: PlatformCapability): boolean {
  return capabilities.includes(required);
}
