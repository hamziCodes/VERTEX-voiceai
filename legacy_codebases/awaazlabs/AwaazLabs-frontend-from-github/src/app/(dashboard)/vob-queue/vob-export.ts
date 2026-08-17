/**
 * §8.4 CSV export for the VOB Queue.
 *
 * SECURITY: the exporter reads ONLY from the pre-projected `VobRowVM`, whose `phoneMasked`
 * comes from `ContactView` and whose raw `phoneE164` is never referenced. So a phone the
 * user has not revealed exports as its mask — the same value the table renders — and a
 * Viewer (who cannot export at all; `recordExport` throws) could never leak one either.
 *
 * The audit row is written by `recordExport` (in data-access) BEFORE the file is produced.
 */

import { VOB_STATUS_LABELS } from '@/shared/status-models';
import type { VobRowVM } from './types';

/** RFC-4180 field escaping: wrap in quotes and double any embedded quote. */
function csvField(value: string): string {
  if (/[",\r\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

/** The exported columns mirror the §8.1 worklist, plus the masked phone (never the raw). */
const COLUMNS = [
  'Patient name',
  'Phone (masked)',
  'Payer',
  'Plan',
  'Status',
  'Linked appointment',
  'Assigned to',
  'Age in queue',
  'Last attempt',
  'Attempts',
  'Location',
] as const;

export function buildVobCsv(rows: readonly VobRowVM[]): string {
  const header = COLUMNS.map(csvField).join(',');
  const body = rows.map((r) =>
    [
      r.patientName,
      r.phoneMasked,
      r.record.payer,
      r.record.plan,
      VOB_STATUS_LABELS[r.effectiveStatus],
      r.linkedApptDate,
      r.effectiveAssignedTo ?? '',
      r.ageLabel,
      r.lastAttempt,
      String(r.attemptsCount),
      r.locationName,
    ]
      .map(csvField)
      .join(','),
  );
  return [header, ...body].join('\r\n');
}

/** Triggers a client-side Blob download. No network, no server round-trip. */
export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
