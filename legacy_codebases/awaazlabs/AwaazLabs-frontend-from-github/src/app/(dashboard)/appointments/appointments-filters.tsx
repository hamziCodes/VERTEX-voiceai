'use client';

/**
 * §5.3 Appointments filter bar: date range, status, source, VOB status, triage flag,
 * language, location, and free-text search on name and phone. Every option label comes
 * from a `*_LABELS` map in status-models.ts; none is hardcoded.
 *
 * The search box's auditing (§5.3 "search is audited in PHI mode") is handled by the
 * parent, which debounces and calls `recordPatientSearch`. This component only reports
 * keystrokes upward.
 */

import React from 'react';
import { Search, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Select, type SelectOption } from '@/components/ui/select';
import {
  APPOINTMENT_SOURCE_LABELS,
  APPOINTMENT_SOURCES,
  APPOINTMENT_STATUS_LABELS,
  APPOINTMENT_STATUSES,
  LANGUAGE_LABELS,
  LANGUAGES,
  TRIAGE_FLAG_LABELS,
  TRIAGE_FLAGS,
  VOB_STATUS_LABELS,
  VOB_STATUSES,
  type AppointmentSource,
  type AppointmentStatus,
  type Language,
  type TriageFlag,
  type VobStatus,
} from '@/shared/status-models';
import type { MockLocation } from '@/mock/schema';

import { DEFAULT_FILTERS, type AppointmentFilters } from './types';

const statusOptions: readonly SelectOption[] = [
  { value: 'all', label: 'All statuses' },
  ...APPOINTMENT_STATUSES.map((s) => ({ value: s, label: APPOINTMENT_STATUS_LABELS[s] })),
];

const sourceOptions: readonly SelectOption[] = [
  { value: 'all', label: 'All sources' },
  ...APPOINTMENT_SOURCES.map((s) => ({ value: s, label: APPOINTMENT_SOURCE_LABELS[s] })),
];

const vobOptions: readonly SelectOption[] = [
  { value: 'all', label: 'All VOB statuses' },
  { value: 'none', label: 'No VOB record' },
  ...VOB_STATUSES.map((s) => ({ value: s, label: VOB_STATUS_LABELS[s] })),
];

const triageOptions: readonly SelectOption[] = [
  { value: 'all', label: 'All triage flags' },
  ...TRIAGE_FLAGS.map((t) => ({ value: t, label: TRIAGE_FLAG_LABELS[t] })),
];

const languageOptions: readonly SelectOption[] = [
  { value: 'all', label: 'All languages' },
  ...LANGUAGES.map((l) => ({ value: l, label: LANGUAGE_LABELS[l] })),
];

export function AppointmentsFilters({
  filters,
  onChange,
  locations,
  showLocationFilter,
}: {
  filters: AppointmentFilters;
  onChange: (next: AppointmentFilters) => void;
  locations: readonly MockLocation[];
  showLocationFilter: boolean;
}) {
  const locationOptions: readonly SelectOption[] = [
    { value: 'all', label: 'All locations' },
    ...locations.map((l) => ({ value: l.id, label: l.name })),
  ];

  const isDirty = JSON.stringify(filters) !== JSON.stringify(DEFAULT_FILTERS);

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative flex-1 min-w-[14rem]">
          <span className="sr-only">Search appointments by name or phone</span>
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <input
            type="search"
            value={filters.search}
            onChange={(e) => onChange({ ...filters, search: e.target.value })}
            placeholder="Search name or phone…"
            className="w-full rounded-md border border-input bg-transparent py-1.5 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>

        {isDirty ? (
          <Button variant="outline" size="sm" onClick={() => onChange(DEFAULT_FILTERS)}>
            <X className="mr-1 h-3 w-3" aria-hidden="true" />
            Clear filters
          </Button>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Select
          aria-label="Filter by status"
          value={filters.status}
          onValueChange={(v) => onChange({ ...filters, status: v as AppointmentStatus | 'all' })}
          options={statusOptions}
        />
        <Select
          aria-label="Filter by source"
          value={filters.source}
          onValueChange={(v) => onChange({ ...filters, source: v as AppointmentSource | 'all' })}
          options={sourceOptions}
        />
        <Select
          aria-label="Filter by VOB status"
          value={filters.vob}
          onValueChange={(v) => onChange({ ...filters, vob: v as VobStatus | 'none' | 'all' })}
          options={vobOptions}
        />
        <Select
          aria-label="Filter by triage flag"
          value={filters.triage}
          onValueChange={(v) => onChange({ ...filters, triage: v as TriageFlag | 'all' })}
          options={triageOptions}
        />
        <Select
          aria-label="Filter by language"
          value={filters.language}
          onValueChange={(v) => onChange({ ...filters, language: v as Language | 'all' })}
          options={languageOptions}
        />
        {showLocationFilter ? (
          <Select
            aria-label="Filter by location"
            value={filters.locationId}
            onValueChange={(v) => onChange({ ...filters, locationId: v })}
            options={locationOptions}
          />
        ) : null}

        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <span>From</span>
            <input
              type="date"
              value={filters.dateFrom}
              onChange={(e) => onChange({ ...filters, dateFrom: e.target.value })}
              aria-label="Filter appointments from date"
              className="rounded-md border border-input bg-transparent px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
          <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <span>To</span>
            <input
              type="date"
              value={filters.dateTo}
              onChange={(e) => onChange({ ...filters, dateTo: e.target.value })}
              aria-label="Filter appointments to date"
              className="rounded-md border border-input bg-transparent px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
        </div>
      </div>
    </div>
  );
}
