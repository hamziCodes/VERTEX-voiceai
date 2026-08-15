'use client';

import React from 'react';
import { AlertTriangle, Clock } from 'lucide-react';
import { Badge, type BadgeVariant } from './badge';
import { VOB_AGING_THRESHOLD_HOURS } from '@/shared/status-models';

/**
 * §8.1 aging SLA indicator: "amber past 24 hours in a non-terminal state, red past 48
 * hours". Thresholds come from `VOB_AGING_THRESHOLD_HOURS`; 24/48 are never hardcoded.
 *
 * Amber is 1.83:1 (THEME_NOTES §5) and MUST NOT carry meaning alone, so the badge always
 * renders an icon + text label (e.g. "26h in queue"); the color is only reinforcement.
 * Also used by §4.6 and §11.2.
 */
export function AgingBadge({
  hours,
  label = 'in queue',
}: {
  hours: number;
  /** Trailing text, e.g. "in queue" -> "26h in queue". */
  label?: string;
}) {
  const isRed = hours >= VOB_AGING_THRESHOLD_HOURS.red;
  const isAmber = !isRed && hours >= VOB_AGING_THRESHOLD_HOURS.amber;

  const variant: BadgeVariant = isRed ? 'destructive' : isAmber ? 'warning' : 'secondary';
  const Icon = isRed || isAmber ? AlertTriangle : Clock;

  return (
    <Badge variant={variant}>
      <span className="inline-flex items-center gap-1">
        <Icon className="h-3 w-3" aria-hidden="true" />
        <span className="tabular-nums">
          {Math.round(hours)}h {label}
        </span>
      </span>
    </Badge>
  );
}
