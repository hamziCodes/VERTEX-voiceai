import { auth, currentUser } from '@clerk/nextjs/server';
import { NextRequest, NextResponse } from 'next/server';

import { DEBUG_ACTOR, DEBUG_BYPASS_AUTH, DEBUG_ROLE } from '@/shared/debug-auth';
import { ROLES, type Role } from '@/shared/status-models';

function roleForApi(role: Role): string {
  if (role === 'OWNER_ADMIN') return 'OWNER';
  if (role === 'MANAGER') return 'ADMIN';
  return 'VIEWER';
}

function roleFromMetadata(metadata: unknown): Role {
  if (typeof metadata !== 'object' || metadata === null) return 'VIEWER';
  const candidate = (metadata as Record<string, unknown>).role;
  if (typeof candidate !== 'string') return 'VIEWER';
  return (ROLES as readonly string[]).includes(candidate) ? (candidate as Role) : 'VIEWER';
}

function contentTypeFor(url: string, upstream: string | null): string {
  if (upstream?.trim()) return upstream;
  const lower = url.toLowerCase();
  if (lower.includes('.wav')) return 'audio/wav';
  if (lower.includes('.mp3')) return 'audio/mpeg';
  if (lower.includes('.m4a') || lower.includes('.mp4')) return 'audio/mp4';
  return 'audio/wav';
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  // DEBUG: skip Clerk session check for local recording playback tests.
  if (!DEBUG_BYPASS_AUTH) {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: { code: 'unauthorized', message: 'Sign in required' } }, { status: 401 });
    }
  }

  const callId = request.nextUrl.searchParams.get('callId')?.trim();
  if (!callId) {
    return NextResponse.json({ error: { code: 'bad_request', message: 'callId is required' } }, { status: 400 });
  }

  const apiUrl = process.env.DASHBOARD_API_URL;
  const secret = process.env.DASHBOARD_API_SECRET;
  if (!apiUrl || !secret) {
    return NextResponse.json(
      { error: { code: 'server_misconfigured', message: 'Dashboard API is not configured' } },
      { status: 500 },
    );
  }

  const user = DEBUG_BYPASS_AUTH ? null : await currentUser();
  const role = user ? roleFromMetadata(user.publicMetadata) : DEBUG_ROLE;
  const actor = user?.primaryEmailAddress?.emailAddress ?? user?.id ?? DEBUG_ACTOR;

  const target = new URL(apiUrl);
  target.searchParams.set('resource', 'recording');
  target.searchParams.set('call_id', callId);

  const meta = await fetch(target, {
    headers: {
      'x-dashboard-secret': secret,
      'x-actor': actor,
      'x-role': roleForApi(role),
      'x-mode': 'PHI_BAA',
    },
    cache: 'no-store',
  });

  const payload = (await meta.json().catch(() => null)) as {
    data?: { recordingUrl?: string };
    error?: { message?: string };
  } | null;

  if (!meta.ok || !payload?.data?.recordingUrl) {
    const status = meta.status === 403 ? 403 : meta.status === 401 ? 401 : 404;
    return NextResponse.json(
      { error: { code: 'not_found', message: payload?.error?.message ?? 'Recording unavailable' } },
      { status },
    );
  }

  const upstreamUrl = payload.data.recordingUrl;
  const range = request.headers.get('range');
  const upstream = await fetch(upstreamUrl, {
    headers: range ? { Range: range } : undefined,
    cache: 'no-store',
  });

  if (!upstream.ok) {
    return NextResponse.json(
      { error: { code: 'upstream_error', message: 'Could not fetch recording from storage' } },
      { status: 502 },
    );
  }

  const headers = new Headers();
  headers.set('Content-Type', contentTypeFor(upstreamUrl, upstream.headers.get('content-type')));
  headers.set('Cache-Control', 'private, max-age=3600');

  for (const name of ['content-length', 'content-range', 'accept-ranges'] as const) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers,
  });
}
