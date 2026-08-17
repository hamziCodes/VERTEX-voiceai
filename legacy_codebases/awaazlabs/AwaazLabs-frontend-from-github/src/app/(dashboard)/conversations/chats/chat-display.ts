/**
 * Display labels for the Chats sub-view (§10.2).
 *
 * The chat session-outcome enum (`CHAT_SESSION_OUTCOMES`) and the chat-message speaker
 * union live in `@/mock/schema` and, unlike the §17 status models, carry no `*_LABELS`
 * map anywhere in the codebase. Rather than re-declare the enum values (which would let an
 * invalid outcome compile), the labels below are keyed by the imported canonical types, so
 * the enum stays the single source of truth and only the human-readable text is added here.
 * The label strings match the values the spec enumerates in §10.2 verbatim.
 */

import type { ChatMessage, ChatSessionOutcome } from '@/mock/schema';
import type { ChatInteractionView } from '@/mock/data-access';

export const CHAT_OUTCOME_LABELS: Readonly<Record<ChatSessionOutcome, string>> = {
  contained: 'Contained',
  resolved: 'Resolved',
  escalated: 'Escalated',
  booked: 'Booked',
};

/** Display label for a chat thread's patient column (support chats are often anonymous). */
export function chatPatientDisplayName(chat: ChatInteractionView): string {
  const identity = chat.contact?.identity ?? null;
  if (identity) {
    const full = `${identity.firstName} ${identity.lastName}`.trim();
    if (full) return full;
  }
  return 'Anonymous visitor';
}

/** Main topic / purpose shown in the chats table. */
export function chatPurposeLabel(chat: ChatInteractionView): string {
  return chat.intent.trim() || 'General support';
}

export function speakerLabel(speaker: ChatMessage['speaker']): string {
  switch (speaker) {
    case 'agent':
      return 'Agent';
    case 'patient':
      return 'Patient';
    case 'human_staff':
      return 'Staff';
    default:
      return speaker;
  }
}
