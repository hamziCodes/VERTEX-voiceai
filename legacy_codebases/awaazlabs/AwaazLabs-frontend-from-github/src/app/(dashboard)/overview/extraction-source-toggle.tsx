'use client';

/**
 * Debug / ops toggle: choose whether Groq transcript extraction writes booking & VOB
 * table columns, or Retell post-call extraction (save-booking + call_analyzed) does.
 *
 * Groq always still runs on transcripts — results are stored in raw_payload either way.
 */

import React, { useCallback, useEffect, useState } from 'react';

import { Banner } from '@/components/ui/banner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { fetchRuntimeSettings, setRuntimeSettings } from '@/lib/dashboard-live';
import { useSession } from '@/shared/session-context';

export function ExtractionSourceToggle(): React.JSX.Element | null {
  const { session } = useSession();
  const isOwner = session.role === 'OWNER_ADMIN';

  const [useGroqTableFill, setUseGroqTableFill] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOwner) return;
    let cancelled = false;
    setLoading(true);
    fetchRuntimeSettings(session)
      .then((settings) => {
        if (!cancelled) setUseGroqTableFill(settings.useGroqTableFill);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load extraction settings.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [session, isOwner]);

  const handleToggle = useCallback(async () => {
    const next = !useGroqTableFill;
    setSaving(true);
    setError(null);
    try {
      const settings = await setRuntimeSettings(session, next);
      setUseGroqTableFill(settings.useGroqTableFill);
    } catch {
      setError('Could not save extraction settings.');
    } finally {
      setSaving(false);
    }
  }, [session, useGroqTableFill]);

  if (!isOwner) return null;

  return (
    <Card>
      <CardHeader className="gap-1">
        <CardTitle className="text-base">Call data extraction (testing)</CardTitle>
        <CardDescription>
          Controls how structured fields reach bookings and the VOB queue after a call. Transcript Groq extraction
          always runs; this toggle only controls whether it writes table columns.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {error ? (
          <Banner variant="destructive" title="Settings error" onDismiss={() => setError(null)}>
            {error}
          </Banner>
        ) : null}

        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 rounded border-input"
            checked={useGroqTableFill}
            disabled={loading || saving}
            onChange={() => void handleToggle()}
            aria-label="Use Groq to fill database tables from transcripts"
          />
          <span className="text-sm text-foreground">
            <span className="font-medium">
              {useGroqTableFill ? 'Groq fills tables' : 'Retell post-call fills tables'}
            </span>
            <span className="mt-1 block text-muted-foreground">
              {useGroqTableFill
                ? 'Groq transcript extraction writes booking / VOB columns during the call (current behavior).'
                : 'Groq still extracts transcripts for audit only. Retell save-booking and call_analyzed post-call data fill the tables instead.'}
            </span>
          </span>
        </label>
      </CardContent>
    </Card>
  );
}
