'use client';

/**
 * §16.6 Notifications (SETTINGS).
 *
 * Full preference matrix: event type × channel × role.
 *   - 8 event types (the exact spec list, below)
 *   - 3 channels: email, SMS, in-app
 *   - 3 roles: the canonical ROLES
 * => 8 × 3 × 3 = 72 cells.
 *
 * "Escalation alerts default on and cannot be fully disabled for the Owner role." Enforced
 * STRUCTURALLY, not merely defaulted: the Owner × escalation-unacknowledged cells are locked
 * on — the checkbox is `disabled` and always `checked`, AND the change handler refuses to
 * mutate a locked cell. There is no code path that turns it off. A visible lock icon and an
 * explanatory note make the constraint legible.
 */

import React, { useState } from 'react';
import { Bell, Lock } from 'lucide-react';

import { Banner } from '@/components/ui/banner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PageHeader } from '@/components/ui/page-header';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ROLE_LABELS, ROLES } from '@/shared/status-models';
import type { Role } from '@/shared/status-models';

/** The exact 8 event types from §16.6, in spec order. */
const EVENT_TYPES = [
  'escalation_unacknowledged',
  'vob_needs_attention_aging',
  'line_health_failure',
  'usage_threshold',
  'weekly_report',
  'monthly_report',
  'knowledge_request_status_change',
  'flag_resolution',
] as const;
type NotificationEvent = (typeof EVENT_TYPES)[number];

const EVENT_LABELS: Readonly<Record<NotificationEvent, string>> = {
  escalation_unacknowledged: 'Escalation unacknowledged',
  vob_needs_attention_aging: 'VOB needs-attention aging',
  line_health_failure: 'Line health failure',
  usage_threshold: 'Usage threshold',
  weekly_report: 'Weekly report',
  monthly_report: 'Monthly report',
  knowledge_request_status_change: 'Knowledge request status change',
  flag_resolution: 'Flag resolution',
};

const CHANNELS = ['email', 'sms', 'in_app'] as const;
type Channel = (typeof CHANNELS)[number];

const CHANNEL_LABELS: Readonly<Record<Channel, string>> = {
  email: 'Email',
  sms: 'SMS',
  in_app: 'In-app',
};

type Matrix = Record<Role, Record<NotificationEvent, Record<Channel, boolean>>>;

/** The one immovable rule: Owner + escalation-unacknowledged is always on. */
function isLocked(role: Role, event: NotificationEvent): boolean {
  return role === 'OWNER_ADMIN' && event === 'escalation_unacknowledged';
}

function buildInitialMatrix(): Matrix {
  const matrix = {} as Matrix;
  for (const role of ROLES) {
    const perEvent = {} as Record<NotificationEvent, Record<Channel, boolean>>;
    for (const event of EVENT_TYPES) {
      const locked = isLocked(role, event);
      perEvent[event] = {
        // Sensible default: email and in-app on, SMS opt-in. Locked cells force SMS on too,
        // and are held on by the render/handler guards regardless of this seed value.
        email: true,
        sms: locked,
        in_app: true,
      };
    }
    matrix[role] = perEvent;
  }
  return matrix;
}

function RoleMatrix({
  role,
  matrix,
  onToggle,
}: {
  role: Role;
  matrix: Matrix;
  onToggle: (role: Role, event: NotificationEvent, channel: Channel) => void;
}) {
  const hasLockedRow = EVENT_TYPES.some((e) => isLocked(role, e));
  return (
    <Card>
      <CardHeader>
        <CardTitle>{ROLE_LABELS[role]}</CardTitle>
      </CardHeader>
      <CardContent>
        <Table caption={`Notification preferences for ${ROLE_LABELS[role]}`}>
          <TableHeader>
            <TableRow>
              <TableHead>Event type</TableHead>
              {CHANNELS.map((c) => (
                <TableHead key={c} className="text-center">
                  {CHANNEL_LABELS[c]}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {EVENT_TYPES.map((event) => {
              const locked = isLocked(role, event);
              return (
                <TableRow key={event}>
                  <TableCell>
                    <span className="inline-flex items-center gap-1.5 text-foreground">
                      {locked ? <Lock className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" /> : null}
                      {EVENT_LABELS[event]}
                    </span>
                  </TableCell>
                  {CHANNELS.map((channel) => {
                    const checked = matrix[role][event][channel];
                    return (
                      <TableCell key={channel} className="text-center">
                        <input
                          type="checkbox"
                          className="h-4 w-4 align-middle accent-primary disabled:opacity-60"
                          checked={locked ? true : checked}
                          disabled={locked}
                          aria-label={
                            locked
                              ? `${CHANNEL_LABELS[channel]} for ${EVENT_LABELS[event]} (${ROLE_LABELS[role]}) — locked on and cannot be disabled`
                              : `${CHANNEL_LABELS[channel]} for ${EVENT_LABELS[event]} (${ROLE_LABELS[role]})`
                          }
                          onChange={() => onToggle(role, event, channel)}
                        />
                      </TableCell>
                    );
                  })}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        {hasLockedRow ? (
          <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Lock className="h-3.5 w-3.5" aria-hidden="true" />
            Escalation-unacknowledged alerts are always on for the Owner/Admin role and cannot be
            disabled on any channel.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function NotificationsClient() {
  const [matrix, setMatrix] = useState<Matrix>(buildInitialMatrix);

  const handleToggle = (role: Role, event: NotificationEvent, channel: Channel) => {
    // Structural guard: a locked cell can never be mutated, regardless of how the handler is
    // invoked. The checkbox is also `disabled`, so this is defense in depth.
    if (isLocked(role, event)) return;
    setMatrix((prev) => ({
      ...prev,
      [role]: {
        ...prev[role],
        [event]: { ...prev[role][event], [channel]: !prev[role][event][channel] },
      },
    }));
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Notifications"
        description="Choose which events notify each role, on which channels. Escalation alerts stay on for the Owner."
      />

      <Banner variant="default" title="Escalation alerts are protected">
        <span className="inline-flex items-center gap-1.5">
          <Bell className="h-4 w-4" aria-hidden="true" />
          Escalation-unacknowledged alerts default on and cannot be fully disabled for the
          Owner/Admin role.
        </span>
      </Banner>

      {ROLES.map((role) => (
        <RoleMatrix key={role} role={role} matrix={matrix} onToggle={handleToggle} />
      ))}
    </div>
  );
}
