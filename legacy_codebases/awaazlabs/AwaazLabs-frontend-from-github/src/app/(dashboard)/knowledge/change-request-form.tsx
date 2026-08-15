'use client';

/**
 * §15.2 change-request workflow — the "Request an update" control that sits on EVERY
 * knowledge block.
 *
 * "Request an update button on every knowledge block: proposed change plus reason,
 *  submitted to Awaaz ops." Submitting calls `recordKnowledgeChangeRequest`, which writes
 *  the `knowledge_change_request` audit event (§2.3). "Every state change notifies the
 *  requester" — surfaced here as a plain notification stub, not a real notification system.
 *
 * There is deliberately NO self-serve editing: this form proposes a change for Awaaz review;
 * it never mutates the knowledge value. The only <textarea>s in the Knowledge tab are the
 * two fields below.
 */

import React, { useId, useState } from 'react';
import { Bell, ClipboardList } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Drawer } from '@/components/ui/drawer';
import { KnowledgeRequestStatusChip } from '@/components/ui/status-chip';
import { recordKnowledgeChangeRequest } from '@/mock/data-access';
import type { KnowledgeCategory } from '@/mock/schema';
import { KNOWLEDGE_REQUEST_STATUSES } from '@/shared/status-models';
import { useSession } from '@/shared/session-context';

export function ChangeRequestForm({
  category,
  categoryLabel,
  blockLabel,
}: {
  category: KnowledgeCategory;
  categoryLabel: string;
  blockLabel: string;
}): React.JSX.Element {
  const { session } = useSession();
  const [open, setOpen] = useState(false);
  const [proposed, setProposed] = useState('');
  const [reason, setReason] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const proposedId = useId();
  const reasonId = useId();

  const canSubmit = proposed.trim() !== '' && reason.trim() !== '';

  function handleOpenChange(next: boolean): void {
    setOpen(next);
    if (!next) {
      // Reset on close so the next block's request starts clean.
      setProposed('');
      setReason('');
      setSubmitted(false);
    }
  }

  function handleSubmit(): void {
    if (!canSubmit) return;
    // Writes the §2.3 `knowledge_change_request` audit event. No knowledge value is mutated.
    recordKnowledgeChangeRequest(session, category);
    setSubmitted(true);
  }

  return (
    <Drawer
      open={open}
      onOpenChange={handleOpenChange}
      title="Request a knowledge update"
      description={`${categoryLabel} · ${blockLabel}`}
      trigger={
        <Button variant="outline" size="sm" aria-label={`Request an update to ${categoryLabel} — ${blockLabel}`}>
          Request an update
        </Button>
      }
      footer={
        submitted ? (
          <div className="flex justify-end">
            <Button variant="outline" onClick={() => handleOpenChange(false)}>
              Close
            </Button>
          </div>
        ) : (
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => handleOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={!canSubmit}>
              Submit to Awaaz ops
            </Button>
          </div>
        )
      }
    >
      {submitted ? (
        <div className="flex flex-col gap-5">
          <div className="flex items-start gap-3 rounded-md border border-border bg-muted/40 p-4">
            <ClipboardList className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div className="flex flex-col gap-1">
              <p className="text-sm font-medium text-foreground">Request submitted to Awaaz ops</p>
              <p className="text-sm text-muted-foreground">
                Nothing has changed in the knowledge base yet. Every change passes Awaaz review before it
                goes live; this request now enters the review workflow.
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium text-foreground">Status pipeline</p>
            <div className="flex flex-wrap items-center gap-2">
              {KNOWLEDGE_REQUEST_STATUSES.map((status, i) => (
                <React.Fragment key={status}>
                  {i > 0 ? <span className="text-muted-foreground" aria-hidden="true">→</span> : null}
                  <KnowledgeRequestStatusChip status={status} />
                </React.Fragment>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">This request is currently at “Requested”.</p>
          </div>

          <div className="flex items-start gap-3 rounded-md border border-border p-4">
            <Bell className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">
              Notification stub: in production a notification would be sent to you at each state change
              (Requested → In review → Scheduled → Live). No notification is actually delivered in this demo.
            </p>
          </div>
        </div>
      ) : (
        <form
          className="flex flex-col gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
        >
          <div className="flex flex-col gap-2">
            <label htmlFor={proposedId} className="text-sm font-medium text-foreground">
              Proposed change
            </label>
            <textarea
              id={proposedId}
              value={proposed}
              onChange={(e) => setProposed(e.target.value)}
              rows={4}
              placeholder="Describe the exact change you would like the agents to reflect."
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor={reasonId} className="text-sm font-medium text-foreground">
              Reason
            </label>
            <textarea
              id={reasonId}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="Why is this change needed? Awaaz ops uses this to review the request."
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <p className="text-xs text-muted-foreground">
            This is a change request, not an edit. The knowledge value stays read-only until Awaaz review
            takes it live.
          </p>
        </form>
      )}
    </Drawer>
  );
}
