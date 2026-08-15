'use client';

/**
 * §8.4 queue-level controls: filters (status, payer, age, assigned-to, location) and bulk
 * retry on the filtered selection. CSV export lives in the client on its own row (right-aligned).
 */

import React from 'react';
import { RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Select, type SelectOption } from '@/components/ui/select';
import { VOB_STATUS_LABELS, type VobStatus } from '@/shared/status-models';

export const AGE_FILTERS = ['all', 'fresh', 'amber', 'red'] as const;
export type AgeFilter = (typeof AGE_FILTERS)[number];

export const AGE_FILTER_LABELS: Readonly<Record<AgeFilter, string>> = {
  all: 'Any age',
  fresh: 'Fresh (< 24h)',
  amber: 'Aging (24–48h)',
  red: 'Overdue (> 48h)',
};

const ALL = '__all__';

function toOptions(values: readonly string[], labelFor: (v: string) => string, allLabel: string): SelectOption[] {
  return [{ value: ALL, label: allLabel }, ...values.map((v) => ({ value: v, label: labelFor(v) }))];
}

export function VobFilters({
  status,
  payer,
  age,
  assignedTo,
  location,
  statuses,
  payers,
  assignees,
  locations,
  showLocationFilter,
  onStatus,
  onPayer,
  onAge,
  onAssignedTo,
  onLocation,
  selectedCount,
  onBulkRetry,
  canAct,
}: {
  status: string;
  payer: string;
  age: AgeFilter;
  assignedTo: string;
  location: string;
  /** Statuses present in the current dataset — avoids options that can never match. */
  statuses: readonly VobStatus[];
  payers: readonly string[];
  assignees: readonly string[];
  locations: readonly { id: string; name: string }[];
  showLocationFilter: boolean;
  onStatus: (v: string) => void;
  onPayer: (v: string) => void;
  onAge: (v: AgeFilter) => void;
  onAssignedTo: (v: string) => void;
  onLocation: (v: string) => void;
  selectedCount: number;
  onBulkRetry: () => void;
  canAct: boolean;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Select
          aria-label="Filter by status"
          value={status}
          onValueChange={onStatus}
          options={toOptions([...statuses], (v) => VOB_STATUS_LABELS[v as VobStatus], 'All statuses')}
        />
        <Select
          aria-label="Filter by payer"
          value={payer}
          onValueChange={onPayer}
          options={toOptions(payers, (v) => v, 'All payers')}
        />
        <Select
          aria-label="Filter by age"
          value={age}
          onValueChange={(v) => onAge(v as AgeFilter)}
          options={AGE_FILTERS.map((a) => ({ value: a, label: AGE_FILTER_LABELS[a] }))}
        />
        <Select
          aria-label="Filter by assignee"
          value={assignedTo}
          onValueChange={onAssignedTo}
          options={[
            { value: ALL, label: 'Anyone' },
            { value: '__unassigned__', label: 'Unassigned' },
            ...assignees.map((a) => ({ value: a, label: a })),
          ]}
        />
        {showLocationFilter ? (
          <Select
            aria-label="Filter by location"
            value={location}
            onValueChange={onLocation}
            options={toOptions(
              locations.map((l) => l.id),
              (id) => locations.find((l) => l.id === id)?.name ?? id,
              'All locations',
            )}
          />
        ) : null}
      </div>

      {canAct ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" disabled={selectedCount === 0} onClick={onBulkRetry}>
            <RefreshCw className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Retry selected{selectedCount > 0 ? ` (${selectedCount})` : ''}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export { ALL as ALL_FILTER_VALUE };
