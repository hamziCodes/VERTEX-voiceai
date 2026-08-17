import type { Metadata } from 'next';

import { ReportsClient } from './reports-client';

export const metadata: Metadata = { title: 'Reports and Exports' };

/**
 * Spec §16.1. Server component wrapper: mode/role/location are switchable client state held
 * by the session context, so the tab's body is a client component.
 */
export default function ReportsPage() {
  return <ReportsClient />;
}
