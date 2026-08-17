/**
 * FIXTURE REGISTRY — the single entry point the data-access layer reads.
 *
 * Keyed by organization id so `getFixture(orgId)` resolves the whole bundle. Nothing here
 * fetches or computes; the fixtures are static, deterministic, anchored to MOCK_NOW_UTC.
 */

import type { OrgFixture } from '@/mock/schema';
import { NORTHSIDE_FIXTURE } from './northside';
import { CEDAR_FIXTURE } from './cedar';

export const FIXTURES: Readonly<Record<string, OrgFixture>> = {
  [NORTHSIDE_FIXTURE.org.id]: NORTHSIDE_FIXTURE,
  [CEDAR_FIXTURE.org.id]: CEDAR_FIXTURE,
};

export function getFixture(orgId: string): OrgFixture {
  const fixture = FIXTURES[orgId];
  if (!fixture) {
    throw new Error(`No fixture registered for organization "${orgId}".`);
  }
  return fixture;
}

export { NORTHSIDE_FIXTURE } from './northside';
export { CEDAR_FIXTURE } from './cedar';
