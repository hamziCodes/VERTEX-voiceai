'use client';

/**
 * §16.1 REPORTS AND EXPORTS (INSIGHTS). Three surfaces, one per spec bullet:
 *   1. Scheduled reports — the weekly/monthly configuration surface.
 *   2. On-demand exports — audited CSV per operational table (Owner/Manager).
 *   3. Business review pack — a print-ready, one-click stakeholder summary.
 */

import React, { useState } from 'react';

import { PageHeader } from '@/components/ui/page-header';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

import { BusinessReviewPack } from './business-review-pack';
import { OnDemandExports } from './on-demand-exports';
import { ScheduledReports } from './scheduled-reports';

export function ReportsClient(): React.JSX.Element {
  const [tab, setTab] = useState('scheduled');

  return (
    <div>
      <PageHeader
        title="Reports and Exports"
        description="Scheduled summaries, audited on-demand CSV exports, and a print-ready monthly business review pack."
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList label="Reports sections" className="mb-4">
          <TabsTrigger value="scheduled">Scheduled reports</TabsTrigger>
          <TabsTrigger value="exports">On-demand exports</TabsTrigger>
          <TabsTrigger value="review">Business review pack</TabsTrigger>
        </TabsList>

        <TabsContent value="scheduled">
          <ScheduledReports />
        </TabsContent>
        <TabsContent value="exports">
          <OnDemandExports />
        </TabsContent>
        <TabsContent value="review">
          <BusinessReviewPack />
        </TabsContent>
      </Tabs>
    </div>
  );
}
