import { Suspense } from 'react';
import type { Metadata } from 'next';

import { VobQueueClient } from './vob-queue-client';
import { TablePageSkeleton } from '@/components/ui/skeleton';

export const metadata: Metadata = { title: 'VOB Queue' };

/** Spec §8. Milestone 1. Suspense boundary is required for `useSearchParams` (§8.1 deep-link). */
export default function VobQueuePage() {
  return (
    <Suspense fallback={<TablePageSkeleton label="Loading the verification worklist…" />}>
      <VobQueueClient />
    </Suspense>
  );
}
