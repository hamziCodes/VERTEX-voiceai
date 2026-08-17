import type { Metadata } from 'next';

import { AppointmentsClient } from './appointments-client';

export const metadata: Metadata = { title: 'Appointments' };

/**
 * Spec §5. Server component wrapper: mode/role/location are switchable client state held by
 * the session context, so the tab's body is a client component (see session-context.tsx).
 */
export default function AppointmentsPage() {
  return <AppointmentsClient />;
}
