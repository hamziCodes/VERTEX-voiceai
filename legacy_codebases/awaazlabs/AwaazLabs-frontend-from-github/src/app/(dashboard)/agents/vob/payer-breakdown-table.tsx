'use client';

/**
 * §7.2 payer breakdown — deliberately the MOST prominent surface on this tab.
 *
 * "This is where a billing company spots problem payers, and the distributor audience is a
 * billing company; make this table prominent." Full-width card, clear heading, sorted by
 * unable-to-verify rate descending by default so problem payers surface first. The
 * unable-to-verify cell carries a red accent when the rate is non-trivial.
 */

import React from 'react';
import { AlertTriangle } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { formatDuration, formatPercent } from '@/lib/format';
import type { PayerRow } from './vob-analytics';

/** Above this unable-to-verify rate a payer is flagged as a problem payer (red accent). */
const PROBLEM_THRESHOLD = 0.15;

function rate(value: number | null): string {
  return value === null ? '—' : formatPercent(value);
}

export function PayerBreakdownTable({ rows }: { rows: readonly PayerRow[] }) {
  return (
    <Card className="border-2 border-border">
      <CardHeader>
        <CardTitle className="text-xl">Payer breakdown</CardTitle>
        <p className="text-sm text-muted-foreground">
          Per-payer verification volume, verified rate, average handle time, and unable-to-verify
          rate. Sorted so problem payers surface first.
        </p>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No verifications in this period.</p>
        ) : (
          <Table caption="Payer breakdown of verification performance">
            <TableHeader>
              <TableRow>
                <TableHead>Payer</TableHead>
                <TableHead className="text-right">Verifications</TableHead>
                <TableHead className="text-right">Verified rate</TableHead>
                <TableHead className="text-right">Avg handle time</TableHead>
                <TableHead className="text-right">Unable to verify</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => {
                const isProblem = (r.unableToVerifyRate ?? 0) >= PROBLEM_THRESHOLD;
                return (
                  <TableRow key={r.payer}>
                    <TableCell className="font-medium text-foreground">{r.payer}</TableCell>
                    <TableCell className="text-right tabular-nums">{r.verifications}</TableCell>
                    <TableCell className="text-right tabular-nums">{rate(r.verifiedRate)}</TableCell>
                    <TableCell className="text-right tabular-nums text-muted-foreground">
                      {r.avgHandleSeconds === null ? '—' : formatDuration(r.avgHandleSeconds)}
                    </TableCell>
                    <TableCell
                      className={cn(
                        'text-right tabular-nums',
                        isProblem ? 'font-semibold text-destructive' : 'text-foreground',
                      )}
                    >
                      <span className="inline-flex items-center justify-end gap-1">
                        {isProblem ? <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" /> : null}
                        {rate(r.unableToVerifyRate)}
                      </span>
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
