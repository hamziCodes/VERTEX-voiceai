'use client';

/**
 * §11 filters. §11 does not enumerate a filter set, so only the filters the spec implies
 * are built: status (open/acknowledged/resolved — the §17 escalation lifecycle), trigger
 * (§11.1 dimension), and location (§2.4 global scope). No filter is invented beyond these.
 *
 * Presentational only — the client owns filter state.
 */

import React from 'react';

import { Select, type SelectOption } from '@/components/ui/select';
import {
  ESCALATION_STATUSES,
  ESCALATION_STATUS_LABELS,
  ESCALATION_TRIGGERS,
  ESCALATION_TRIGGER_LABELS,
} from '@/shared/status-models';

export const ALL_FILTER_VALUE = '__all__';

const STATUS_OPTIONS: SelectOption[] = [
  { value: ALL_FILTER_VALUE, label: 'All statuses' },
  { value: 'pending', label: 'Pending (not resolved)' },
  ...ESCALATION_STATUSES.map((s) => ({ value: s, label: ESCALATION_STATUS_LABELS[s] })),
];

const TRIGGER_OPTIONS: SelectOption[] = [
  { value: ALL_FILTER_VALUE, label: 'All triggers' },
  ...ESCALATION_TRIGGERS.map((t) => ({ value: t, label: ESCALATION_TRIGGER_LABELS[t] })),
];

export function EscalationsFilters({
  status,
  trigger,
  location,
  locations,
  showLocationFilter,
  onStatus,
  onTrigger,
  onLocation,
}: {
  status: string;
  trigger: string;
  location: string;
  locations: readonly { id: string; name: string }[];
  showLocationFilter: boolean;
  onStatus: (v: string) => void;
  onTrigger: (v: string) => void;
  onLocation: (v: string) => void;
}): React.JSX.Element {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select aria-label="Filter by status" value={status} onValueChange={onStatus} options={STATUS_OPTIONS} />
      <Select aria-label="Filter by trigger" value={trigger} onValueChange={onTrigger} options={TRIGGER_OPTIONS} />
      {showLocationFilter ? (
        <Select
          aria-label="Filter by location"
          value={location}
          onValueChange={onLocation}
          options={[
            { value: ALL_FILTER_VALUE, label: 'All locations' },
            ...locations.map((l) => ({ value: l.id, label: l.name })),
          ]}
        />
      ) : null}
    </div>
  );
}
