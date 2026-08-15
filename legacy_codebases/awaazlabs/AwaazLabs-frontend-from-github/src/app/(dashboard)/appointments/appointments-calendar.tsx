'use client';

/**
 * §5.5 Calendar view (secondary). Day and week AGENDA rendering of the same filtered data.
 * No drag-to-reschedule in this build (rescheduling is an agent/EHR action, per §5.5).
 *
 * The agenda is forward-looking: it groups the filtered appointments by their local date
 * (§2.7 — each row in its own location's timezone) across a 1-day (Day) or 7-day (Week)
 * window anchored at MOCK_NOW. Rows outside the window remain reachable in the table.
 */

import React, { useMemo, useState } from 'react';

import { EmptyState } from '@/components/ui/empty-state';
import { AppointmentStatusChip, TriageChip } from '@/components/ui/status-chip';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { formatTime } from '@/lib/format';
import { timezoneFor } from '@/lib/format';
import { mockNow } from '@/mock/orgs';
import type { AppointmentView, Session } from '@/mock/data-access';

import { dateKeyWindow, localDateKey } from './types';

function dayLabel(key: string): string {
  const d = new Date(`${key}T12:00:00.000Z`);
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'UTC',
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(d);
}

export function AppointmentsCalendar({
  rows,
  session,
  onRowClick,
}: {
  rows: readonly AppointmentView[];
  session: Session;
  onRowClick: (id: string) => void;
}) {
  const [range, setRange] = useState<'day' | 'week'>('week');

  const windowKeys = useMemo(() => dateKeyWindow(mockNow(), range === 'day' ? 1 : 7), [range]);

  const grouped = useMemo(() => {
    const keySet = new Set(windowKeys);
    const byDay = new Map<string, AppointmentView[]>();
    for (const appt of rows) {
      const key = localDateKey(appt.startsAtUtc, timezoneFor(session.orgId, appt.locationId));
      if (!keySet.has(key)) continue;
      const bucket = byDay.get(key) ?? [];
      bucket.push(appt);
      byDay.set(key, bucket);
    }
    for (const bucket of byDay.values()) {
      bucket.sort((a, b) => new Date(a.startsAtUtc).getTime() - new Date(b.startsAtUtc).getTime());
    }
    return byDay;
  }, [rows, windowKeys, session.orgId]);

  const hasAny = windowKeys.some((k) => (grouped.get(k)?.length ?? 0) > 0);

  return (
    <div className="flex flex-col gap-4">
      <Tabs value={range} onValueChange={(v) => setRange(v === 'day' ? 'day' : 'week')}>
        <TabsList label="Calendar range">
          <TabsTrigger value="day">Day</TabsTrigger>
          <TabsTrigger value="week">Week</TabsTrigger>
        </TabsList>
      </Tabs>

      {!hasAny ? (
        <EmptyState
          title="Nothing scheduled in this window"
          description="No appointments match the current filters within the selected day or week. The full table lists appointments outside this window."
        />
      ) : (
        <div className="flex flex-col gap-4">
          {windowKeys.map((key) => {
            const dayRows = grouped.get(key) ?? [];
            return (
              <section key={key} className="rounded-lg border border-border bg-card">
                <h3 className="border-b border-border px-4 py-2 text-sm font-semibold text-foreground">
                  {dayLabel(key)}
                  <span className="ml-2 font-normal text-muted-foreground">
                    {dayRows.length === 0
                      ? 'No appointments'
                      : `${dayRows.length} appointment${dayRows.length === 1 ? '' : 's'}`}
                  </span>
                </h3>
                {dayRows.length > 0 ? (
                  <ul className="divide-y divide-border">
                    {dayRows.map((appt) => {
                      const tz = timezoneFor(session.orgId, appt.locationId);
                      const identity = appt.contact.identity;
                      const name = identity ? `${identity.firstName} ${identity.lastName}` : '—';
                      return (
                        <li key={appt.id}>
                          <button
                            type="button"
                            onClick={() => onRowClick(appt.id)}
                            className="flex w-full flex-wrap items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-muted/30"
                          >
                            <span className="w-20 shrink-0 tabular-nums font-medium text-foreground">
                              {formatTime(appt.startsAtUtc, tz)}
                            </span>
                            <span className="flex-1 min-w-[8rem] text-foreground">{name}</span>
                            <span className="min-w-[8rem] text-muted-foreground">{appt.serviceInterest}</span>
                            <TriageChip status={appt.triage} />
                            <AppointmentStatusChip status={appt.status} />
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
