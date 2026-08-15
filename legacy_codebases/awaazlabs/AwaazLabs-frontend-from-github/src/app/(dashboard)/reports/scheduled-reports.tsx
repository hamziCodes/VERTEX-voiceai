'use client';

/**
 * §16.1 — "Scheduled reports: weekly and monthly PDF summaries (appointments, VOB,
 * conversations, quality, reviews, campaigns) emailed to configured recipients; per-location
 * and consolidated variants."
 *
 * This is the CONFIGURATION surface only. There is no email service and no PDF generator in a
 * frontend-only build, and the UI says so plainly rather than faking a broken download.
 * A Viewer sees the configuration read-only (§16.1 degraded state).
 */

import React, { useCallback, useState } from 'react';
import { CalendarClock, Mail, Plus, X } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { canExport } from '@/mock/data-access';
import { useSession } from '@/shared/session-context';

type Frequency = 'weekly' | 'monthly';
type Variant = 'consolidated' | 'per_location';

/** The six summary sections named in §16.1, in the spec's order. */
const SECTIONS = [
  { key: 'appointments', label: 'Appointments' },
  { key: 'vob', label: 'VOB' },
  { key: 'conversations', label: 'Conversations' },
  { key: 'quality', label: 'Quality' },
  { key: 'reviews', label: 'Reviews' },
  { key: 'campaigns', label: 'Campaigns' },
] as const;

const FREQUENCY_OPTIONS = [
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
];

const VARIANT_OPTIONS = [
  { value: 'consolidated', label: 'Consolidated (all locations)' },
  { value: 'per_location', label: 'Per-location (one report per location)' },
];

export function ScheduledReports(): React.JSX.Element {
  const { session, org } = useSession();
  const canEdit = canExport(session);

  const [frequency, setFrequency] = useState<Frequency>('weekly');
  const [variant, setVariant] = useState<Variant>('consolidated');
  const [sections, setSections] = useState<ReadonlySet<string>>(
    () => new Set(SECTIONS.map((s) => s.key)),
  );
  const [recipients, setRecipients] = useState<readonly string[]>([]);
  const [draft, setDraft] = useState('');
  const [saved, setSaved] = useState(false);

  const toggleSection = useCallback((key: string) => {
    setSaved(false);
    setSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const addRecipient = useCallback(() => {
    const value = draft.trim();
    if (value === '' || !value.includes('@')) return;
    setSaved(false);
    setRecipients((prev) => (prev.includes(value) ? prev : [...prev, value]));
    setDraft('');
  }, [draft]);

  const removeRecipient = useCallback((email: string) => {
    setSaved(false);
    setRecipients((prev) => prev.filter((r) => r !== email));
  }, []);

  return (
    <Card>
      <CardHeader className="gap-2">
        <CardTitle className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          Scheduled reports
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          Configure the weekly or monthly summary. Delivery — PDF generation and email — is
          handled by Awaaz operations; nothing is generated or sent from this screen.
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-6">
        {!canEdit ? (
          <Banner variant="default" title="Read-only">
            Your role can view the scheduled-report configuration but cannot change it. Editing is
            available to Owner and Manager roles.
          </Banner>
        ) : null}

        <div className="grid gap-6 sm:grid-cols-2">
          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium text-foreground">Frequency</span>
            <Select
              value={frequency}
              onValueChange={(v) => {
                setSaved(false);
                setFrequency(v as Frequency);
              }}
              options={FREQUENCY_OPTIONS}
              disabled={!canEdit}
              aria-label="Report frequency"
            />
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium text-foreground">Variant</span>
            <Select
              value={variant}
              onValueChange={(v) => {
                setSaved(false);
                setVariant(v as Variant);
              }}
              options={VARIANT_OPTIONS}
              disabled={!canEdit}
              aria-label="Report variant"
            />
            <span className="text-xs text-muted-foreground">
              {org.locations.length > 1
                ? `${org.locations.length} locations configured for this organization.`
                : 'This organization has a single location; both variants produce one report.'}
            </span>
          </label>
        </div>

        <fieldset className="flex flex-col gap-3" disabled={!canEdit}>
          <legend className="text-sm font-medium text-foreground">Sections included</legend>
          <div className="flex flex-wrap gap-3">
            {SECTIONS.map((s) => {
              const checked = sections.has(s.key);
              return (
                <label
                  key={s.key}
                  className={cn(
                    'flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors',
                    checked ? 'border-border bg-muted/60 text-foreground' : 'border-border bg-transparent text-muted-foreground',
                    !canEdit && 'cursor-not-allowed opacity-70',
                  )}
                >
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-primary"
                    checked={checked}
                    onChange={() => toggleSection(s.key)}
                    disabled={!canEdit}
                  />
                  {s.label}
                </label>
              );
            })}
          </div>
        </fieldset>

        <div className="flex flex-col gap-3">
          <span className="text-sm font-medium text-foreground">Recipients</span>
          {recipients.length > 0 ? (
            <ul className="flex flex-wrap gap-2">
              {recipients.map((email) => (
                <li key={email}>
                  <Badge variant="outline" className="gap-1.5">
                    <Mail className="h-3 w-3" aria-hidden="true" />
                    {email}
                    {canEdit ? (
                      <button
                        type="button"
                        aria-label={`Remove ${email}`}
                        onClick={() => removeRecipient(email)}
                        className="ml-0.5 inline-flex h-4 w-4 items-center justify-center rounded hover:bg-foreground/10"
                      >
                        <X className="h-3 w-3" aria-hidden="true" />
                      </button>
                    ) : null}
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No recipients configured yet.</p>
          )}

          {canEdit ? (
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="email"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addRecipient();
                  }
                }}
                placeholder="name@clinic.com"
                aria-label="Add recipient email"
                className="min-w-0 flex-1 rounded-md border border-input bg-transparent px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground"
              />
              <Button variant="secondary" onClick={addRecipient} disabled={!draft.includes('@')}>
                <Plus className="mr-1 h-4 w-4" aria-hidden="true" />
                Add
              </Button>
            </div>
          ) : null}
        </div>

        {canEdit ? (
          <div className="flex items-center gap-3">
            <Button onClick={() => setSaved(true)}>Save configuration</Button>
            {saved ? (
              <span className="text-sm text-muted-foreground" role="status">
                Saved. Awaaz ops will deliver the {frequency} report to {recipients.length} recipient
                {recipients.length === 1 ? '' : 's'}.
              </span>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
