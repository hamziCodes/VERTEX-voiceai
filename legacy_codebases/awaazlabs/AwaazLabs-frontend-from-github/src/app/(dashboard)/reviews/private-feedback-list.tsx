'use client';

/**
 * Private feedback list — spec §13.1 ("appear in this tab as a separate list for the clinic
 * to action") and §13.2 ("date, patient, summary, source call link, status").
 *
 * Fed from `fixture.privateFeedback`: negative-experience routing captured AFTER the review
 * ask, never instead of it (the compliance rule). One implementation, rendered by both the
 * Review Taker agent tab (§13.1) and the Reviews growth tab (§13.2).
 *
 * NON-PHI: private feedback names patients and links to their call recording, so the
 * patient-level rows and the source-call link are withheld — only an aggregate count
 * renders. The branch is on `canSeePatientRows(session)` from the data-access layer, which
 * is the structural gate, not a cosmetic one.
 */

import React from 'react';
import Link from 'next/link';
import { ArrowUpRight, MessageSquareWarning } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { canSeePatientRows } from '@/mock/data-access';
import type { Session } from '@/mock/data-access';
import { formatDate, timezoneFor } from '@/lib/format';
import { scopeToLocation } from '@/lib/metrics';
import { getFixture } from '@/mock/fixtures';
import type { PatientContact, PrivateFeedback } from '@/mock/schema';

function patientName(contact: PatientContact | undefined): string {
  if (!contact || !contact.identity) return 'Unknown patient';
  return `${contact.identity.firstName} ${contact.identity.lastName}`;
}

export function PrivateFeedbackList({
  session,
  className,
}: {
  session: Session;
  className?: string;
}): React.JSX.Element {
  const fixture = getFixture(session.orgId);
  const items = scopeToLocation(fixture.privateFeedback, session);
  const contacts = new Map(fixture.contacts.map((c) => [c.id, c]));

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>
          <span className="inline-flex items-center gap-2">
            <MessageSquareWarning className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
            Private feedback to action
          </span>
        </CardTitle>
        <CardDescription>
          Patients who expressed a negative experience were routed to private feedback capture after the
          review ask — never in place of it. Action these directly; they are not published as reviews.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <EmptyState
            icon={<MessageSquareWarning className="h-8 w-8" />}
            title="No private feedback"
            description="Negative-experience routing has produced no items in this scope."
          />
        ) : !canSeePatientRows(session) ? (
          // NON-PHI: patient-level rows and the source-call link are withheld.
          <p className="text-sm text-muted-foreground">
            {items.length} private feedback item{items.length === 1 ? '' : 's'} in this scope. Patient-level
            detail and the source-call link are hidden in NON-PHI mode.
          </p>
        ) : (
          <Table caption="Private feedback items">
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Patient</TableHead>
                <TableHead>Summary</TableHead>
                <TableHead>Source call</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item: PrivateFeedback) => {
                const tz = timezoneFor(session.orgId, item.locationId);
                return (
                  <TableRow key={item.id}>
                    <TableCell className="whitespace-nowrap text-muted-foreground tabular-nums">
                      {formatDate(item.atUtc, tz)}
                    </TableCell>
                    <TableCell className="whitespace-nowrap font-medium text-foreground">
                      {patientName(contacts.get(item.contactId))}
                    </TableCell>
                    <TableCell className="text-foreground">{item.summary}</TableCell>
                    <TableCell className="whitespace-nowrap">
                      <RowOpenButtonLink interactionId={item.sourceInteractionId} />
                    </TableCell>
                    <TableCell>
                      <Badge variant={item.status === 'new' ? 'outline' : 'secondary'}>
                        {item.status === 'new' ? 'New' : 'Actioned'}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * §13.2 "source call link". Deep-links to the Calls sub-view with the interaction pre-selected
 * (`?interaction=` auto-opens that row's drawer, per the Calls sub-view). It is a real link,
 * not a `RowOpenButton`, because it navigates rather than opening an in-page drawer.
 */
function RowOpenButtonLink({ interactionId }: { interactionId: string }): React.JSX.Element {
  return (
    <Link
      href={`/conversations/calls?interaction=${interactionId}`}
      className="inline-flex items-center gap-1 text-sm font-medium text-foreground hover:underline"
    >
      View call
      <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
    </Link>
  );
}
