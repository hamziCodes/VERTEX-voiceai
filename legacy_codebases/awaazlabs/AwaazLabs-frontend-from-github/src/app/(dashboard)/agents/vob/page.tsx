import type { Metadata } from 'next';

import { VobAgentClient } from './vob-agent-client';

export const metadata: Metadata = { title: 'VOB Agent' };

/** Spec §7. Milestone 1. */
export default function VobAgentPage() {
  return <VobAgentClient />;
}
