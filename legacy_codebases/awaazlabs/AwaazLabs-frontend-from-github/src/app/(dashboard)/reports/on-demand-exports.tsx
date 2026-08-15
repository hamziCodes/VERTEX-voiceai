'use client';

/**
 * §16.1 — "On-demand CSV export per operational table (Appointments, VOB Queue,
 * Conversations, Campaigns contacts), role-gated to Owner and Manager, every export audited
 * with row-count and filter parameters recorded."
 *
 * Gating is structural, not cosmetic:
 *   - A Viewer never sees a button (`canExport` is false) — and even if one were forced,
 *     `recordExport` throws `PermissionDeniedError`.
 *   - In NON-PHI mode the readers return `{ kind: 'aggregate' }`, so patient-level rows do
 *     not exist to export; those exports are withheld rather than emitting an empty file.
 *   - The CSV builders read only projected views (masked phone), never the raw number.
 */

import React, { useCallback, useMemo, useState } from 'react';
import { Download, FileDown, Lock } from 'lucide-react';

import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatCount } from '@/lib/format';
import { mockNow } from '@/mock/orgs';
import { getFixture } from '@/mock/fixtures';
import {
  canExport,
  canSeePatientRows,
  listAppointments,
  listCalls,
  listChats,
  listVobRecords,
  PermissionDeniedError,
  recordExport,
  type ContactView,
} from '@/mock/data-access';
import { useSession } from '@/shared/session-context';

import {
  buildAppointmentsCsv,
  buildCampaignContactsCsv,
  buildConversationsCsv,
  buildVobCsv,
  downloadCsv,
  type CampaignContactRow,
} from './csv';

interface ExportRow {
  readonly key: string;
  readonly table: string;
  readonly label: string;
  readonly description: string;
  readonly rowCount: number;
  readonly buildCsv: () => string;
}

export function OnDemandExports(): React.JSX.Element {
  const { session } = useSession();
  const fixture = getFixture(session.orgId);
  const [error, setError] = useState<string | null>(null);
  const [lastExported, setLastExported] = useState<string | null>(null);

  const patientRowsVisible = canSeePatientRows(session);

  // Projected identity views, keyed by contact id, gathered from the readers that expose a
  // ContactView. This is how the campaign-contacts export obtains a *masked* phone without
  // ever touching the raw number: it reuses the same projection the tables render.
  const contactViews = useMemo<ReadonlyMap<string, ContactView>>(() => {
    const map = new Map<string, ContactView>();
    const appts = listAppointments(fixture, session);
    if (appts.kind === 'rows') appts.rows.forEach((r) => map.set(r.contact.id, r.contact));
    const vob = listVobRecords(fixture, session);
    if (vob.kind === 'rows') vob.rows.forEach((r) => map.set(r.contact.id, r.contact));
    const calls = listCalls(fixture, session);
    if (calls.kind === 'rows') calls.rows.forEach((r) => r.contact && map.set(r.contact.id, r.contact));
    const chats = listChats(fixture, session);
    if (chats.kind === 'rows') chats.rows.forEach((r) => r.contact && map.set(r.contact.id, r.contact));
    return map;
  }, [fixture, session]);

  const exports = useMemo<readonly ExportRow[]>(() => {
    if (!patientRowsVisible) return [];

    const appts = listAppointments(fixture, session);
    const vob = listVobRecords(fixture, session);
    const calls = listCalls(fixture, session);
    const chats = listChats(fixture, session);

    const apptRows = appts.kind === 'rows' ? appts.rows : [];
    const vobRows = vob.kind === 'rows' ? vob.rows : [];
    const callRows = calls.kind === 'rows' ? calls.rows : [];
    const chatRows = chats.kind === 'rows' ? chats.rows : [];

    // §2.4 the global location filter already scopes every reader; campaigns are scoped here
    // to match, since they are read straight from the fixture.
    const campaignContacts: CampaignContactRow[] = fixture.campaigns
      .filter((c) => session.locationId === null || c.locationId === session.locationId)
      .flatMap((campaign) =>
        campaign.contacts.map((contact) => ({
          campaign,
          contact,
          contactView: contactViews.get(contact.contactId) ?? null,
        })),
      );

    return [
      {
        key: 'appointments',
        table: 'appointments',
        label: 'Appointments',
        description: 'Every appointment in scope, with masked phone, status, source, and booking agent.',
        rowCount: apptRows.length,
        buildCsv: () => buildAppointmentsCsv(apptRows, session.orgId),
      },
      {
        key: 'vob_queue',
        table: 'vob_queue',
        label: 'VOB Queue',
        description: 'Verification records with payer, plan, status, assignment, and attempts.',
        rowCount: vobRows.length,
        buildCsv: () => buildVobCsv(vobRows, session.orgId),
      },
      {
        key: 'conversations',
        table: 'conversations',
        label: 'Conversations',
        description: 'Calls and chats unified into one interaction log with outcome and grade.',
        rowCount: callRows.length + chatRows.length,
        buildCsv: () => buildConversationsCsv(callRows, chatRows, session.orgId),
      },
      {
        key: 'campaign_contacts',
        table: 'campaign_contacts',
        label: 'Campaign contacts',
        description: 'Per-contact rows across campaigns: status, attempts, last outcome, opt-out.',
        rowCount: campaignContacts.length,
        buildCsv: () => buildCampaignContactsCsv(campaignContacts),
      },
    ];
  }, [fixture, session, patientRowsVisible, contactViews]);

  const filterParams = useMemo<Record<string, string>>(
    () => ({ location: session.locationId ?? 'all', mode: session.mode }),
    [session.locationId, session.mode],
  );

  const handleExport = useCallback(
    (row: ExportRow) => {
      try {
        // Audit first (records row-count + filters), then produce the file (§16.1).
        recordExport(session, row.table, row.rowCount, filterParams);
        downloadCsv(`${row.table}-${mockNow().toISOString().slice(0, 10)}.csv`, row.buildCsv());
        setError(null);
        setLastExported(row.label);
      } catch (e) {
        setLastExported(null);
        setError(
          e instanceof PermissionDeniedError
            ? 'Export is not permitted for your role.'
            : 'Export failed. No file was produced.',
        );
      }
    },
    [session, filterParams],
  );

  // §16.1 degraded state — Viewer: no export buttons anywhere.
  if (!canExport(session)) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            On-demand exports
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            CSV exports of operational tables are available to Owner and Manager roles. Your role
            has read-only access to the dashboards but cannot export patient-level data.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="gap-2">
        <CardTitle className="flex items-center gap-2">
          <FileDown className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          On-demand exports
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          Each export is written client-side as a CSV and recorded in the Audit Log with its
          row count and the active filter parameters. Unrevealed phone numbers export as their
          mask.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error ? (
          <Banner variant="destructive" onDismiss={() => setError(null)}>
            {error}
          </Banner>
        ) : null}
        {lastExported ? (
          <Banner variant="default" onDismiss={() => setLastExported(null)}>
            {`${lastExported} exported. An audit event was recorded.`}
          </Banner>
        ) : null}

        {!patientRowsVisible ? (
          <Banner variant="default" title="NON-PHI mode">
            Patient-level CSV exports (Appointments, VOB Queue, Conversations, Campaign contacts)
            are unavailable in NON-PHI mode. Switch to PHI mode to export operational tables.
          </Banner>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {exports.map((row) => (
              <li key={row.key} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="font-medium text-foreground">
                    {row.label}{' '}
                    <span className="text-sm font-normal text-muted-foreground">
                      ({formatCount(row.rowCount)} row{row.rowCount === 1 ? '' : 's'})
                    </span>
                  </p>
                  <p className="text-sm text-muted-foreground">{row.description}</p>
                </div>
                <Button
                  variant="outline"
                  onClick={() => handleExport(row)}
                  disabled={row.rowCount === 0}
                  aria-label={`Export ${row.label} as CSV`}
                >
                  <Download className="mr-2 h-4 w-4" aria-hidden="true" />
                  Export CSV
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
