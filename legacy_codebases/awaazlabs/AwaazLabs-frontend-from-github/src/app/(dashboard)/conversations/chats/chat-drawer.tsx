'use client';

/**
 * §10.2 Chat thread detail. Sub-items: full transcript with timestamps, handoff markers
 * where a human took over (`ChatMessage.isHandoffMarker` → a clear "Handed off to staff"
 * divider), linked appointment, and a flag button.
 *
 * Same audit rules as call playback: `viewTranscript` fires when the drawer opens. Gating
 * is structural — a Viewer / NON-PHI session receives `messages: null`, so there is no
 * transcript to reach and none is rendered.
 */

import React, { useEffect } from 'react';
import Link from 'next/link';
import { CalendarDays, ExternalLink, Flag } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Drawer } from '@/components/ui/drawer';
import { formatDateTime, timezoneFor } from '@/lib/format';
import { viewTranscript, type ChatInteractionView, type Session } from '@/mock/data-access';
import { APPOINTMENT_SOURCE_LABELS } from '@/shared/status-models';

import { CHAT_OUTCOME_LABELS, chatPatientDisplayName, chatPurposeLabel, speakerLabel } from './chat-display';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border py-4 first:border-t-0 first:pt-0">
      <h3 className="mb-3 text-sm font-semibold text-foreground">{title}</h3>
      {children}
    </section>
  );
}

export function ChatDrawer({
  chat,
  session,
  flagged,
  onFlag,
  onClose,
}: {
  chat: ChatInteractionView;
  session: Session;
  flagged: boolean;
  onFlag: () => void;
  onClose: () => void;
}): React.JSX.Element {
  const tz = timezoneFor(session.orgId, chat.locationId);
  const name = chatPatientDisplayName(chat);
  const purpose = chatPurposeLabel(chat);
  const messages = chat.messages;

  // §10.2 "Same audit rules as call playback" — opening the transcript is an audited event.
  useEffect(() => {
    if (!messages) return;
    try {
      viewTranscript(session, chat.id);
    } catch {
      /* refused in data-access; nothing to surface */
    }
  }, [session, chat.id, messages]);

  return (
    <Drawer
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={name}
      description={`${purpose} · ${APPOINTMENT_SOURCE_LABELS[chat.channel]} · ${CHAT_OUTCOME_LABELS[chat.outcome]}`}
    >
      {/* Full transcript with timestamps and handoff markers. */}
      {messages ? (
        <Section title="Transcript">
          {messages.length === 0 ? (
            <p className="text-sm text-muted-foreground">No messages in this thread.</p>
          ) : (
            <ol className="flex flex-col gap-3">
              {messages.map((msg, i) => (
                <React.Fragment key={`${msg.at}-${i}`}>
                  {msg.isHandoffMarker ? (
                    <li className="flex items-center gap-3 py-1" aria-label="Handed off to staff">
                      <span className="h-px flex-1 bg-border" aria-hidden="true" />
                      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Handed off to staff
                      </span>
                      <span className="h-px flex-1 bg-border" aria-hidden="true" />
                    </li>
                  ) : null}
                  <li className="flex flex-col gap-0.5">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {speakerLabel(msg.speaker)}
                      </span>
                      <span className="text-xs tabular-nums text-muted-foreground">{formatDateTime(msg.at, tz)}</span>
                    </div>
                    <p className="text-sm text-foreground">{msg.text}</p>
                  </li>
                </React.Fragment>
              ))}
            </ol>
          )}
        </Section>
      ) : (
        <Section title="Transcript">
          <p className="text-sm text-muted-foreground">
            Chat transcripts require Manager or Owner access in PHI mode.
          </p>
        </Section>
      )}

      {/* Linked appointment. */}
      <Section title="Linked records">
        {chat.linked.appointmentId ? (
          <Link href="/appointments" className="inline-flex items-center gap-1.5 text-sm text-foreground hover:underline">
            <CalendarDays className="h-4 w-4" aria-hidden="true" />
            Appointment created
            <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
          </Link>
        ) : (
          <p className="text-sm text-muted-foreground">No linked records for this chat.</p>
        )}
      </Section>

      {/* Flag this interaction (§12.5). */}
      <Section title="Flag for review">
        {flagged ? (
          <p className="inline-flex items-center gap-1.5 text-sm text-foreground">
            <Flag className="h-4 w-4" aria-hidden="true" />
            Flagged for Qualicall priority review.
          </p>
        ) : (
          <Button variant="outline" size="sm" onClick={onFlag}>
            <Flag className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Flag this interaction
          </Button>
        )}
      </Section>
    </Drawer>
  );
}
