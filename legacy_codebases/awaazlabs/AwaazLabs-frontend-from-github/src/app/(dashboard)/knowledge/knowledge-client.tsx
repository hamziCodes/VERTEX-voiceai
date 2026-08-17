'use client';

/**
 * §15 AGENT KNOWLEDGE TAB.
 *
 * Purpose (§15): "answers the clinic owner's biggest trust question: what is this system
 * telling my patients. Read-only with a controlled change workflow."
 *
 * §15.1 renders all eight knowledge categories (iterated from `KNOWLEDGE_CATEGORIES`, never
 * hardcoded), structured and per-location where applicable. §15.2 attaches a change-request
 * control to every block, tracks request status through requested → in_review → scheduled →
 * live, and lists version history.
 *
 * SCOPE BOUNDARY (§15.2): "Deliberately no self-serve editing in this build." Every value
 * below is read-only text. There is no inline edit, no contentEditable, no save control on
 * any block — the only inputs are the two textareas inside the change-request form.
 *
 * Aggregate-by-nature: no patient name, phone, recording, or transcript appears here.
 */

import React from 'react';
import { BookOpen, Building2, History, Lock, MapPin } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { KnowledgeRequestStatusChip } from '@/components/ui/status-chip';
import { formatDateTime, timezoneFor } from '@/lib/format';
import { getFixture } from '@/mock/fixtures';
import { KNOWLEDGE_CATEGORIES, type KnowledgeBlock, type KnowledgeCategory } from '@/mock/schema';
import { useSession } from '@/shared/session-context';

import { KNOWLEDGE_CATEGORY_LABELS } from './categories';
import { ChangeRequestForm } from './change-request-form';

/** §2.4: per-location blocks respect the active global location filter; org-wide always shows. */
function blockInScope(block: KnowledgeBlock, locationId: string | null): boolean {
  if (block.locationId === null) return true;
  if (locationId === null) return true;
  return block.locationId === locationId;
}

function EntryList({ entries }: { entries: KnowledgeBlock['entries'] }): React.JSX.Element {
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[minmax(0,14rem)_1fr]">
      {entries.map((entry) => (
        <React.Fragment key={entry.label}>
          <dt className="text-sm font-medium text-muted-foreground">{entry.label}</dt>
          {/* Read-only value — plain text, never an input or editable region (§15.2). */}
          <dd className="text-sm text-foreground">{entry.value}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

function KnowledgeBlockView({
  block,
  category,
  categoryLabel,
  locationName,
}: {
  block: KnowledgeBlock;
  category: KnowledgeCategory;
  categoryLabel: string;
  locationName: string | null;
}): React.JSX.Element {
  const scopeLabel = locationName ?? 'All locations';
  return (
    <div className="flex flex-col gap-3 rounded-md border border-border p-4">
      <div className="flex items-start justify-between gap-3">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          {locationName ? (
            <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <Building2 className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {scopeLabel}
        </span>
        {/* §15.2: a change-request control on EVERY block. */}
        <ChangeRequestForm category={category} categoryLabel={categoryLabel} blockLabel={scopeLabel} />
      </div>
      <EntryList entries={block.entries} />
    </div>
  );
}

export function KnowledgeClient(): React.JSX.Element {
  const { session, org } = useSession();
  const fixture = getFixture(session.orgId);

  const tz = timezoneFor(session.orgId, session.locationId ?? org.locations[0]?.id ?? '');
  const locationName = (id: string): string => org.locations.find((l) => l.id === id)?.name ?? id;

  const blocksInScope = fixture.knowledgeBlocks.filter((b) => blockInScope(b, session.locationId));
  const hasAnyKnowledge = blocksInScope.length > 0;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Agent Knowledge"
        description="Everything the agents tell your patients, across all eight knowledge categories. Read-only with a controlled change workflow — every change passes Awaaz review."
      />

      <div className="flex items-start gap-3 rounded-md border border-border bg-muted/40 p-4">
        <Lock className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm text-muted-foreground">
          Deliberately no self-serve editing: uncontrolled knowledge edits are how the clinical boundary and
          compliance language degrade. Values here are read-only; use “Request an update” on any block to
          propose a change for Awaaz review.
        </p>
      </div>

      {/* §15.1 — the knowledge view. All eight categories, iterated from KNOWLEDGE_CATEGORIES. */}
      <section className="flex flex-col gap-6" aria-label="Knowledge categories">
        <h2 className="inline-flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
          <BookOpen className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
          Knowledge view
        </h2>

        {!hasAnyKnowledge ? (
          <EmptyState
            title="No knowledge configured yet"
            description="Once this clinic's services, pricing, hours, and other knowledge are loaded, they appear here across all eight categories."
          />
        ) : (
          KNOWLEDGE_CATEGORIES.map((category) => {
            const categoryLabel = KNOWLEDGE_CATEGORY_LABELS[category];
            const blocks = blocksInScope.filter((b) => b.category === category);
            const orgWide = blocks.filter((b) => b.locationId === null);
            const perLocation = blocks.filter((b) => b.locationId !== null);

            return (
              <Card key={category}>
                <CardHeader>
                  <CardTitle>{categoryLabel}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  {blocks.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No entries configured for this category yet.
                    </p>
                  ) : (
                    <>
                      {orgWide.map((block, i) => (
                        <KnowledgeBlockView
                          key={`org-${i}`}
                          block={block}
                          category={category}
                          categoryLabel={categoryLabel}
                          locationName={null}
                        />
                      ))}
                      {perLocation.map((block, i) => (
                        <KnowledgeBlockView
                          key={`loc-${block.locationId}-${i}`}
                          block={block}
                          category={category}
                          categoryLabel={categoryLabel}
                          locationName={block.locationId ? locationName(block.locationId) : null}
                        />
                      ))}
                    </>
                  )}
                </CardContent>
              </Card>
            );
          })
        )}
      </section>

      {/* §15.2 — change requests, status tracking, and version history. */}
      <section className="flex flex-col gap-4" aria-label="Change requests and version history">
        <h2 className="inline-flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
          <History className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
          Change requests &amp; version history
        </h2>
        <p className="text-sm text-muted-foreground">
          Every state change (Requested → In review → Scheduled → Live) notifies the requester. Notification
          delivery is stubbed in this demo.
        </p>

        {fixture.knowledgeRequests.length === 0 ? (
          <EmptyState
            title="No change requests yet"
            description="When someone requests a knowledge update, it appears here with its current status and full version history."
          />
        ) : (
          <div className="flex flex-col gap-4">
            {fixture.knowledgeRequests.map((req) => (
              <Card key={req.id}>
                <CardContent className="flex flex-col gap-4 pt-6">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex flex-col gap-1">
                      <p className="text-sm font-medium text-foreground">{req.proposedChange}</p>
                      <p className="text-sm text-muted-foreground">
                        {KNOWLEDGE_CATEGORY_LABELS[req.category]} · {req.reason}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Requested by {req.requestedBy} · {formatDateTime(req.requestedAtUtc, tz)}
                      </p>
                    </div>
                    <KnowledgeRequestStatusChip status={req.status} />
                  </div>

                  <div className="flex flex-col gap-2 border-t border-border pt-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Version history
                    </p>
                    <ol className="flex flex-col gap-2">
                      {req.history.map((h, i) => (
                        <li key={`${h.status}-${i}`} className="flex items-center gap-3">
                          <KnowledgeRequestStatusChip status={h.status} />
                          <span className="text-xs text-muted-foreground">{formatDateTime(h.at, tz)}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
