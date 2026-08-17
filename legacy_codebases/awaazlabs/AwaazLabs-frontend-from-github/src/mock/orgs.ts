/**
 * MOCK ORGANIZATIONS — spec §2.4, guide Part F.4.
 *
 * FROZEN FILE (Foundation).
 *
 * "Two mock organizations: one single-location, one multi-location, to prove the location
 * filter behavior both ways." (guide F.4)
 *
 * §2.4: "Single-location clinics see no filter." The single-location org exists precisely
 * to exercise that branch — without it, the hidden-filter path would never render.
 */

import type { BusinessHours, MockLocation, MockOrganization } from './schema';

/** Mon–Fri 08:00–17:00, Sat 09:00–13:00. Minutes from midnight, local to the location. */
const STANDARD_HOURS: readonly BusinessHours[] = [
  { day: 1, openMinute: 8 * 60, closeMinute: 17 * 60 },
  { day: 2, openMinute: 8 * 60, closeMinute: 17 * 60 },
  { day: 3, openMinute: 8 * 60, closeMinute: 17 * 60 },
  { day: 4, openMinute: 8 * 60, closeMinute: 17 * 60 },
  { day: 5, openMinute: 8 * 60, closeMinute: 17 * 60 },
  { day: 6, openMinute: 9 * 60, closeMinute: 13 * 60 },
];

const US_HOLIDAYS_2026: readonly string[] = [
  '2026-01-01',
  '2026-05-25',
  '2026-07-03',
  '2026-09-07',
  '2026-11-26',
  '2026-12-25',
];

/* ----------------------------------------------------------------------------------
 * Org 1 — Northside Dental. Multi-location (3), PHI-BAA tier.
 * The primary demo org: exercises the location filter, the revenue estimate card, and
 * the multi-location review comparison table (§13.2).
 * -------------------------------------------------------------------------------- */

export const NORTHSIDE_LOCATIONS: readonly MockLocation[] = [
  {
    id: 'loc_north',
    name: 'Northside — Main',
    timezone: 'America/Chicago',
    businessHours: STANDARD_HOURS,
    holidays: US_HOLIDAYS_2026,
    // §2.8: two-party consent state. Drives the §10.1 disclosure event on call records.
    recordingConsentMode: 'two_party',
    escalationForwardingNumber: '+13125550188',
  },
  {
    id: 'loc_west',
    name: 'Northside — Westgate',
    timezone: 'America/Chicago',
    businessHours: STANDARD_HOURS,
    holidays: US_HOLIDAYS_2026,
    recordingConsentMode: 'one_party',
    escalationForwardingNumber: '+13125550199',
  },
  {
    id: 'loc_south',
    name: 'Northside — Southpark',
    timezone: 'America/Denver',
    businessHours: STANDARD_HOURS,
    holidays: US_HOLIDAYS_2026,
    recordingConsentMode: 'one_party',
    escalationForwardingNumber: '+17205550132',
  },
];

export const NORTHSIDE_DENTAL: MockOrganization = {
  id: 'org_northside',
  name: 'Northside Dental Group',
  locations: NORTHSIDE_LOCATIONS,
  // §4.3: set, so the revenue-recovered estimate card renders.
  avgAppointmentValueUsd: 285,
  // §4.1: true, so the no-show/cancellation card renders.
  outcomeDataAvailable: true,
  planMinutes: 12000,
  planChatSessions: 4000,
};

/* ----------------------------------------------------------------------------------
 * Org 2 — Cedar Family Clinic. Single-location.
 *
 * Deliberately configured to prove three degradation paths the spec requires and which
 * would otherwise never render:
 *   - §2.4  location filter is hidden entirely (one location)
 *   - §4.3  revenue card hides (avgAppointmentValueUsd = null)
 *   - §4.1  no-show card hides rather than showing a misleading zero
 *           (outcomeDataAvailable = false) — see BUILD_NOTES.md § B9
 * -------------------------------------------------------------------------------- */

export const CEDAR_LOCATIONS: readonly MockLocation[] = [
  {
    id: 'loc_cedar',
    name: 'Cedar Family Clinic',
    timezone: 'America/Los_Angeles',
    businessHours: STANDARD_HOURS,
    holidays: US_HOLIDAYS_2026,
    recordingConsentMode: 'one_party',
    escalationForwardingNumber: '+14155550170',
  },
];

export const CEDAR_FAMILY: MockOrganization = {
  id: 'org_cedar',
  name: 'Cedar Family Clinic',
  locations: CEDAR_LOCATIONS,
  avgAppointmentValueUsd: null,
  outcomeDataAvailable: false,
  planMinutes: 2500,
  planChatSessions: 500,
};

export const ALL_ORGS: readonly MockOrganization[] = [NORTHSIDE_DENTAL, CEDAR_FAMILY];

export const DEFAULT_ORG_ID = NORTHSIDE_DENTAL.id;

export function getOrgById(orgId: string): MockOrganization | undefined {
  return ALL_ORGS.find((o) => o.id === orgId);
}

export function getLocationById(orgId: string, locationId: string): MockLocation | undefined {
  return getOrgById(orgId)?.locations.find((l) => l.id === locationId);
}

/**
 * The "now" the entire mock dataset is anchored to.
 *
 * Every fixture timestamp is expressed relative to this instant, so "booked today",
 * "aging past 48 hours", and "trailing 30 days" are stable and reproducible instead of
 * drifting with the wall clock. Without a fixed anchor, the seeded 48-hour-red VOB row
 * would silently age out of its own demo state.
 */
export const MOCK_NOW_UTC = '2026-07-09T15:20:00.000Z';

export function mockNow(): Date {
  return new Date(MOCK_NOW_UTC);
}
