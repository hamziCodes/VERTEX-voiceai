'use client';

import React from 'react';
import { Badge, type BadgeVariant } from './badge';
import {
  APPOINTMENT_STATUS_LABELS,
  CALL_DISPOSITION_LABELS,
  CAMPAIGN_STATUS_LABELS,
  ESCALATION_STATUS_LABELS,
  FLAG_STATUS_LABELS,
  KNOWLEDGE_REQUEST_STATUS_LABELS,
  OPTIMIZATION_EVENT_STATUS_LABELS,
  REVIEW_REQUEST_STATUS_LABELS,
  TRIAGE_FLAG_LABELS,
  VOB_CHIP_LABELS,
  VOB_STATUS_LABELS,
  isVobNeedsAttention,
  type AppointmentStatus,
  type CallDisposition,
  type CampaignStatus,
  type EscalationStatus,
  type FlagStatus,
  type KnowledgeRequestStatus,
  type OptimizationEventStatus,
  type ReviewRequestStatus,
  type TriageFlag,
  type VobStatus,
} from '@/shared/status-models';

/**
 * Status chips. Each component takes its canonical union type — never `string` — so an
 * invalid status cannot compile. Labels come exclusively from the `*_LABELS` maps in
 * status-models.ts; no label is hardcoded here.
 *
 * Color policy: the spec mandates a red accent in exactly two places — triage High/Urgent
 * (§5.2 / §6.2) and VOB needs-attention states (§4.2 / §7.3). Those use `destructive`.
 * Every other status renders neutral (`secondary`); introducing unvalidated color meaning
 * elsewhere would violate THEME_NOTES.
 */

function Chip({ variant, label }: { variant: BadgeVariant; label: string }) {
  return <Badge variant={variant}>{label}</Badge>;
}

export function AppointmentStatusChip({ status }: { status: AppointmentStatus }) {
  return <Chip variant="secondary" label={APPOINTMENT_STATUS_LABELS[status]} />;
}

export function VobStatusChip({ status, abbreviated = false }: { status: VobStatus; abbreviated?: boolean }) {
  // §5.2 Appointments column uses the abbreviated VOB_CHIP_LABELS; it is a Partial map, so
  // fall back to the full label for statuses it does not abbreviate.
  const label = abbreviated ? VOB_CHIP_LABELS[status] ?? VOB_STATUS_LABELS[status] : VOB_STATUS_LABELS[status];
  // §4.2 / §7.3 — every terminal state other than `verified` is a needs-attention state
  // and carries a red accent.
  const variant: BadgeVariant = isVobNeedsAttention(status) ? 'destructive' : 'secondary';
  return <Chip variant={variant} label={label} />;
}

export function EscalationStatusChip({ status }: { status: EscalationStatus }) {
  return <Chip variant="secondary" label={ESCALATION_STATUS_LABELS[status]} />;
}

export function FlagStatusChip({ status }: { status: FlagStatus }) {
  return <Chip variant="secondary" label={FLAG_STATUS_LABELS[status]} />;
}

export function OptimizationStatusChip({ status }: { status: OptimizationEventStatus }) {
  return <Chip variant="secondary" label={OPTIMIZATION_EVENT_STATUS_LABELS[status]} />;
}

export function CallDispositionChip({ status }: { status: CallDisposition }) {
  return <Chip variant="secondary" label={CALL_DISPOSITION_LABELS[status]} />;
}

export function TriageChip({ status }: { status: TriageFlag }) {
  // §5.2 / §6.2: red accents on High and Urgent.
  const variant: BadgeVariant = status === 'high' || status === 'urgent' ? 'destructive' : 'secondary';
  return <Chip variant={variant} label={TRIAGE_FLAG_LABELS[status]} />;
}

export function CampaignStatusChip({ status }: { status: CampaignStatus }) {
  return <Chip variant="secondary" label={CAMPAIGN_STATUS_LABELS[status]} />;
}

export function ReviewRequestStatusChip({ status }: { status: ReviewRequestStatus }) {
  return <Chip variant="secondary" label={REVIEW_REQUEST_STATUS_LABELS[status]} />;
}

export function KnowledgeRequestStatusChip({ status }: { status: KnowledgeRequestStatus }) {
  return <Chip variant="secondary" label={KNOWLEDGE_REQUEST_STATUS_LABELS[status]} />;
}
