'use client';

/**
 * §4.3 Section C — Revenue recovered (estimate). A single card.
 *
 * `revenueRecoveredEstimate` returns null when the org has no configured average
 * appointment value, in which case the whole section hides (§4.3, never a misleading $0).
 * The card is labelled an estimate; its tooltip states the formula, the live inputs, and
 * the "recovered no-show" definition verbatim from BUILD_NOTES B5 so the reader is never
 * misled. Configuration lives in Organization settings, which the card links to.
 */

import React from 'react';
import { StatCard } from '@/components/ui/stat-card';
import { formatUsd } from '@/lib/format';
import type { RevenueEstimate } from '@/lib/metrics';

/** BUILD_NOTES B5, verbatim. */
const RECOVERED_NO_SHOW_DEFINITION =
  'Recovered no-show: an appointment whose status reached no_show, and for which a subsequent appointment was later booked for the same contact within the reporting period.';

export function RevenueSection({ estimate }: { estimate: RevenueEstimate | null }): React.JSX.Element | null {
  if (estimate === null) return null;

  const tooltip = [
    'Estimate = (after-hours bookings + reengagement bookings + recovered no-shows) × average appointment value.',
    `Inputs this month: after-hours ${estimate.afterHoursBookings}, reengagement ${estimate.reengagementBookings}, recovered no-shows ${estimate.recoveredNoShows}, average appointment value ${formatUsd(estimate.avgAppointmentValueUsd)}.`,
    RECOVERED_NO_SHOW_DEFINITION,
  ].join(' ');

  return (
    <section aria-labelledby="overview-revenue">
      <h2 id="overview-revenue" className="pb-3 text-lg font-semibold tracking-tight text-foreground">
        Revenue recovered (estimate)
      </h2>

      <div className="grid grid-cols-1 sm:max-w-md">
        <StatCard
          label="Estimated revenue recovered this month"
          value={formatUsd(estimate.totalUsd)}
          format="text"
          tooltip={tooltip}
          href="/settings/organization"
          linkLabel="Configure average appointment value in Organization settings"
        />
      </div>
    </section>
  );
}
