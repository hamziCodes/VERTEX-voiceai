/**
 * §13.1 REVIEW TAKER — derivations.
 *
 * The tab renders through the standard agent template (§2.6), so this file owns every
 * number the template's stat cards, funnel and distribution consume. All aggregate: it
 * reads review-request records (NoPhi) and appointment counts, never patient identity, so
 * the funnel and stats survive NON-PHI mode exactly as the VOB tab's do.
 *
 * Rates return `null` (rendered as "—") rather than NaN or a misleading 0% when their
 * denominator is zero — `ratio()` from '@/lib/format' enforces that in one place.
 */

import { ratio } from '@/lib/format';
import { scopeToLocation } from '@/lib/metrics';
import type { OrgFixture, ReviewRequest } from '@/mock/schema';
import type { Session } from '@/mock/data-access';
import type { ReviewRequestStatus } from '@/shared/status-models';

/* ==================================================================================
 * The eligibility ladder — the spine of the eight-stage funnel.
 *
 * A review request carries one status: the furthest point it reached, or a terminal
 * branch. `ladderIndex` maps each status to how far along the linear ask pipeline it
 * travelled, so cumulative "reached at least stage k" counts are well-defined.
 *
 * `declined` and `opt_out` both sit at the ASK stage (index 3): per the compliance rule
 * every eligible patient receives the ask, so declining or opting out both happen at or
 * after the ask is delivered — never before it. Neither reached `agreed`.
 * ================================================================================== */

/** Linear stages the ladder index points into (indices 0..6). */
const LADDER_STAGES = [
  'eligible',
  'called',
  'reached',
  'asked',
  'agreed',
  'link_sent',
  'posted',
] as const;

function ladderIndex(status: ReviewRequestStatus): number {
  switch (status) {
    case 'eligible':
      return 0;
    case 'called':
      return 1;
    case 'reached':
      return 2;
    case 'asked':
    case 'declined':
    case 'opt_out':
      return 3;
    case 'agreed':
      return 4;
    case 'link_sent':
      return 5;
    case 'posted':
      return 6;
  }
}

/** Count requests that reached at least `stage` on the linear ladder. */
function atLeast(requests: readonly ReviewRequest[], stage: (typeof LADDER_STAGES)[number]): number {
  const k = LADDER_STAGES.indexOf(stage);
  return requests.filter((r) => ladderIndex(r.status) >= k).length;
}

/* ==================================================================================
 * The eight-stage funnel (spec §13.1, verbatim enumeration)
 * ================================================================================== */

export interface FunnelStageDatum {
  readonly key: string;
  readonly label: string;
  readonly count: number;
}

export function reviewFunnel(fixture: OrgFixture, session: Session): readonly FunnelStageDatum[] {
  const requests = scopeToLocation(fixture.reviewRequests, session);
  const completedAppointments = scopeToLocation(fixture.appointments, session).filter(
    (a) => a.status === 'completed',
  ).length;

  return [
    { key: 'completed_appointments', label: 'Completed appointments', count: completedAppointments },
    { key: 'eligible', label: 'Eligible', count: atLeast(requests, 'eligible') },
    { key: 'called', label: 'Called', count: atLeast(requests, 'called') },
    { key: 'reached', label: 'Reached', count: atLeast(requests, 'reached') },
    { key: 'asked', label: 'Review ask delivered', count: atLeast(requests, 'asked') },
    { key: 'agreed', label: 'Agreed', count: atLeast(requests, 'agreed') },
    { key: 'link_sent', label: 'Link sent (SMS)', count: atLeast(requests, 'link_sent') },
    { key: 'posted', label: 'Review posted (attributed)', count: atLeast(requests, 'posted') },
  ];
}

/* ==================================================================================
 * Stat cards
 * ================================================================================== */

export interface ReviewStats {
  readonly callsPlaced: number;
  readonly reached: number;
  readonly reachRate: number | null;
  readonly asksDelivered: number;
  readonly agreed: number;
  readonly agreementRate: number | null;
  readonly linkSent: number;
  readonly linkSendRate: number | null;
  readonly linkClicked: number;
  readonly linkClickRate: number | null;
  readonly posted: number;
  readonly avgRating: number | null;
  readonly optOuts: number;
  readonly avgCallDurationSeconds: number | null;
}

export function reviewStats(fixture: OrgFixture, session: Session): ReviewStats {
  const requests = scopeToLocation(fixture.reviewRequests, session);

  const callsPlaced = atLeast(requests, 'called');
  const reached = atLeast(requests, 'reached');
  const asksDelivered = atLeast(requests, 'asked');
  const agreed = atLeast(requests, 'agreed');
  const linkSent = atLeast(requests, 'link_sent');
  const linkClicked = requests.filter((r) => ladderIndex(r.status) >= 5 && r.linkClicked).length;

  const postedRequests = requests.filter((r) => r.status === 'posted');
  const ratingSum = postedRequests.reduce((acc, r) => acc + (r.postedRating ?? 0), 0);

  const called = requests.filter((r) => r.callDurationSeconds !== null);
  const durationSum = called.reduce((acc, r) => acc + (r.callDurationSeconds ?? 0), 0);

  return {
    callsPlaced,
    reached,
    reachRate: ratio(reached, callsPlaced),
    asksDelivered,
    agreed,
    agreementRate: ratio(agreed, asksDelivered),
    linkSent,
    linkSendRate: ratio(linkSent, agreed),
    linkClicked,
    linkClickRate: ratio(linkClicked, linkSent),
    posted: postedRequests.length,
    avgRating: ratio(ratingSum, postedRequests.length),
    optOuts: requests.filter((r) => r.status === 'opt_out').length,
    avgCallDurationSeconds: ratio(durationSum, called.length),
  };
}

/* ==================================================================================
 * Outcome distribution — the §2.6 template's required "one distribution component".
 *
 * Every scoped review request lands in exactly one of four outcome groups, so the bar
 * sums to the whole population and complements the funnel's cumulative view.
 * ================================================================================== */

export interface OutcomeCounts {
  readonly posted: number;
  readonly inPipeline: number;
  readonly declined: number;
  readonly optOut: number;
}

export function outcomeCounts(fixture: OrgFixture, session: Session): OutcomeCounts {
  const requests = scopeToLocation(fixture.reviewRequests, session);
  const posted = requests.filter((r) => r.status === 'posted').length;
  const declined = requests.filter((r) => r.status === 'declined').length;
  const optOut = requests.filter((r) => r.status === 'opt_out').length;
  return {
    posted,
    inPipeline: requests.length - posted - declined - optOut,
    declined,
    optOut,
  };
}

/** True when the agent has no review activity at all (e.g. the single-location Cedar org). */
export function hasReviewActivity(fixture: OrgFixture, session: Session): boolean {
  const requests = scopeToLocation(fixture.reviewRequests, session);
  const completed = scopeToLocation(fixture.appointments, session).filter((a) => a.status === 'completed');
  return requests.length > 0 || completed.length > 0;
}
