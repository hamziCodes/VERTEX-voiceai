'use client';

/**
 * §16.5 Lines and Numbers (SETTINGS).
 *
 *  - Connected phone numbers and WhatsApp senders, grouped PER LOCATION.
 *  - Per-line health indicator (green/red) with last-checked timestamp. Health is a STATUS,
 *    so it is never carried by color alone: every indicator ships an icon + text label. The
 *    theme has no green success token (THEME_NOTES), so a healthy line reads as a neutral
 *    "Healthy" chip with a check icon; a failing line uses the reserved `destructive` token
 *    with an alert icon and "Failing" text. At least one seeded line is unhealthy — it also
 *    drives the §4.6 Overview attention banner.
 *  - Escalation forwarding target, per location.
 *  - Recording-consent mode per location (one-party / two-party). loc_north is two_party,
 *    which is what makes §10.1 render a consent-disclosure event for its calls.
 */

import React, { useMemo } from 'react';
import { CheckCircle2, MessageCircle, Mic, Phone, PhoneForwarded, XCircle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PageHeader } from '@/components/ui/page-header';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatDateTime } from '@/lib/format';
import { getFixture } from '@/mock/fixtures';
import { useSession } from '@/shared/session-context';
import type { RecordingConsentMode } from '@/shared/status-models';
import type { MockLocation, PhoneLine } from '@/mock/schema';

/** No shipped *_LABELS map exists for RecordingConsentMode; these are display strings only. */
const CONSENT_MODE_LABELS: Readonly<Record<RecordingConsentMode, string>> = {
  one_party: 'One-party consent',
  two_party: 'Two-party consent',
};

const LINE_KIND_LABELS: Readonly<Record<PhoneLine['kind'], string>> = {
  voice: 'Voice',
  whatsapp: 'WhatsApp',
};

function HealthChip({ healthy }: { healthy: boolean }) {
  return healthy ? (
    <Badge variant="secondary">
      <span className="inline-flex items-center gap-1">
        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
        Healthy
      </span>
    </Badge>
  ) : (
    <Badge variant="destructive">
      <span className="inline-flex items-center gap-1">
        <XCircle className="h-3 w-3" aria-hidden="true" />
        Failing
      </span>
    </Badge>
  );
}

function LocationLines({ location, lines }: { location: MockLocation; lines: readonly PhoneLine[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{location.name}</CardTitle>
        <div className="mt-2 flex flex-wrap gap-4 text-sm">
          <span className="inline-flex items-center gap-2">
            <Mic className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            <span className="text-muted-foreground">Recording consent</span>
            <span className="font-medium text-foreground">
              {CONSENT_MODE_LABELS[location.recordingConsentMode]}
            </span>
          </span>
          <span className="inline-flex items-center gap-2">
            <PhoneForwarded className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            <span className="text-muted-foreground">Escalation forwarding</span>
            <span className="font-medium text-foreground tabular-nums">
              {location.escalationForwardingNumber}
            </span>
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {lines.length === 0 ? (
          <p className="text-sm text-muted-foreground">No numbers connected at this location.</p>
        ) : (
          <Table caption={`Connected numbers for ${location.name}`}>
            <TableHeader>
              <TableRow>
                <TableHead>Number</TableHead>
                <TableHead>Channel</TableHead>
                <TableHead>Health</TableHead>
                <TableHead>Last checked</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell className="font-medium text-foreground tabular-nums">{line.number}</TableCell>
                  <TableCell>
                    <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                      {line.kind === 'voice' ? (
                        <Phone className="h-4 w-4" aria-hidden="true" />
                      ) : (
                        <MessageCircle className="h-4 w-4" aria-hidden="true" />
                      )}
                      {LINE_KIND_LABELS[line.kind]}
                    </span>
                  </TableCell>
                  <TableCell>
                    <HealthChip healthy={line.healthy} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDateTime(line.lastCheckedUtc, location.timezone)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

export function LinesClient() {
  const { session, org } = useSession();
  const fixture = getFixture(session.orgId);

  const linesByLocation = useMemo<ReadonlyMap<string, readonly PhoneLine[]>>(() => {
    const map = new Map<string, PhoneLine[]>();
    for (const line of fixture.lines) {
      const list = map.get(line.locationId) ?? [];
      list.push(line);
      map.set(line.locationId, list);
    }
    return map;
  }, [fixture.lines]);

  const unhealthyCount = fixture.lines.filter((l) => !l.healthy).length;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Lines and Numbers"
        description="Connected phone numbers and WhatsApp senders per location, each with a health check, plus escalation forwarding and recording-consent mode."
      />

      {unhealthyCount > 0 ? (
        <p className="text-sm text-destructive">
          <span className="inline-flex items-center gap-1.5">
            <XCircle className="h-4 w-4" aria-hidden="true" />
            {unhealthyCount} line{unhealthyCount === 1 ? '' : 's'} currently failing a health check.
          </span>
        </p>
      ) : null}

      {org.locations.map((location) => (
        <LocationLines key={location.id} location={location} lines={linesByLocation.get(location.id) ?? []} />
      ))}
    </div>
  );
}
