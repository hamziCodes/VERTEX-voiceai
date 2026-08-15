'use client';

import { useCallback, useSyncExternalStore } from 'react';

import {
  getDashboardResourceSnapshot,
  invalidateDashboardResource,
  prefetchDashboardResource,
  subscribeDashboardResource,
  type DashboardResource,
  type DashboardResourceData,
} from '@/lib/dashboard-cache';
import { useSession } from '@/shared/session-context';

interface UseDashboardResourceResult<R extends DashboardResource> {
  readonly data: DashboardResourceData[R] | null;
  readonly error: string | null;
  readonly isLoading: boolean;
  readonly isRefreshing: boolean;
  readonly refresh: () => void;
  readonly invalidate: () => void;
}

function useDashboardResource<R extends DashboardResource>(resource: R): UseDashboardResourceResult<R> {
  const { session } = useSession();

  const subscribe = useCallback(
    (onStoreChange: () => void) => subscribeDashboardResource(resource, session, onStoreChange),
    [resource, session],
  );

  const getSnapshot = useCallback(
    () => getDashboardResourceSnapshot(resource, session),
    [resource, session],
  );

  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  const refresh = useCallback(() => {
    prefetchDashboardResource(resource, session);
  }, [resource, session]);

  const invalidate = useCallback(() => {
    invalidateDashboardResource(resource, session);
  }, [resource, session]);

  return {
    data: snapshot.data,
    error: snapshot.error,
    isLoading: snapshot.isLoading,
    isRefreshing: snapshot.isRefreshing,
    refresh,
    invalidate,
  };
}

export function useLiveAppointments() {
  return useDashboardResource('appointments');
}

export function useLiveEscalations() {
  return useDashboardResource('escalations');
}

export function useLiveCalls() {
  return useDashboardResource('calls');
}

export function useLiveChats() {
  return useDashboardResource('chats');
}

export function useLiveNotifications() {
  return useDashboardResource('notifications');
}

export function useLiveVobQueue() {
  return useDashboardResource('vob_queue');
}
