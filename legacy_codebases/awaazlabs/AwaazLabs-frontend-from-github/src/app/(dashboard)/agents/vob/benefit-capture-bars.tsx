'use client';

/**
 * §7.1 "Benefit capture completeness %, decomposed into THREE sub-bars: copay captured,
 * deductible captured, out-of-pocket-max captured." Completeness tracks clean-claim rate;
 * industry target 95%+. Rendered as three labelled bars, never a single number.
 *
 * Colors are tokens only: recessive `bg-muted` track, `bg-primary` fill, dashed
 * `border-border` target marker at 95%.
 */

import React from 'react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatPercent } from '@/lib/format';
import type { BenefitCapture } from './vob-analytics';

const TARGET = 0.95;

function SubBar({ label, rate }: { label: string; rate: number | null }) {
  const pct = rate ?? 0;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums text-foreground">
          {rate === null ? '—' : formatPercent(rate)}
        </span>
      </div>
      <div
        className="relative h-2.5 w-full overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={`${label}: ${rate === null ? 'no data' : formatPercent(rate)} captured (target ${formatPercent(TARGET)})`}
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.round(pct * 100)}%` }} />
        {/* 95% target marker */}
        <div
          className="absolute top-0 h-full border-l border-dashed border-border"
          style={{ left: `${TARGET * 100}%` }}
          aria-hidden="true"
        />
      </div>
    </div>
  );
}

export function BenefitCaptureBars({ capture }: { capture: BenefitCapture }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Benefit capture completeness</CardTitle>
        <p className="text-sm text-muted-foreground">
          Share of verifications with each benefit captured. Completeness tracks clean-claim rate;
          the industry target is 95%+ (dashed marker).
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <SubBar label="Copay captured" rate={capture.copay} />
        <SubBar label="Deductible captured" rate={capture.deductible} />
        <SubBar label="Out-of-pocket max captured" rate={capture.outOfPocketMax} />
      </CardContent>
    </Card>
  );
}
