import { downloadCsv } from '@/app/(dashboard)/reports/csv';
import { canExport, PermissionDeniedError, recordExport, type Session } from '@/mock/data-access';

/** §16.1 audited CSV download. Returns an error message on failure, null on success. */
export function runCsvExport(
  session: Session,
  table: string,
  rowCount: number,
  filters: Readonly<Record<string, string>>,
  filename: string,
  csv: string,
): string | null {
  if (!canExport(session)) {
    return 'Export not permitted for this role.';
  }
  try {
    recordExport(session, table, rowCount, filters);
    downloadCsv(filename, csv);
    return null;
  } catch (e) {
    return e instanceof PermissionDeniedError ? 'Export not permitted for this role.' : 'Export failed.';
  }
}

export function filtersToParams(filters: Readonly<Record<string, string | undefined | boolean>>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === '') continue;
    out[key] = typeof value === 'string' ? value : String(value);
  }
  return out;
}
