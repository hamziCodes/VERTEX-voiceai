import { NextRequest, NextResponse } from 'next/server';

const ALLOWED_RESOURCES = new Set([
  'appointments',
  'stats',
  'appointment',
  'calls',
  'chats',
  'escalations',
  'escalation',
  'escalation_stats',
  'vob_queue',
  'vob_stats',
  'notifications',
  'runtime_settings',
]);

const ALLOWED_ACTIONS = new Set([
  'reveal_phone',
  'status_change',
  'add_note',
  'record_search',
  'acknowledge_escalation',
  'escalation_note',
  'resolve_escalation',
  'vob_retry',
  'vob_resolve',
  'vob_escalate',
  'vob_add_note',
  'set_runtime_settings',
]);

function roleForApi(role: string | null): string {
  if (role === 'OWNER_ADMIN') return 'OWNER';
  if (role === 'MANAGER') return 'ADMIN';
  if (role === 'VIEWER') return 'VIEWER';
  return 'VIEWER';
}

function modeForApi(mode: string | null): string {
  return mode === 'NON_PHI' ? 'NON_PHI' : 'PHI_BAA';
}

function apiConfig(): { url: string; secret: string } | NextResponse {
  const url = process.env.DASHBOARD_API_URL;
  const secret = process.env.DASHBOARD_API_SECRET;
  if (!url || !secret) {
    return NextResponse.json(
      { error: { code: 'server_misconfigured', message: 'Dashboard API is not configured' } },
      { status: 500 },
    );
  }
  return { url, secret };
}

function forwardHeaders(request: NextRequest, secret: string): HeadersInit {
  return {
    'content-type': 'application/json',
    'x-dashboard-secret': secret,
    'x-actor': request.headers.get('x-actor') ?? 'unknown',
    'x-role': roleForApi(request.headers.get('x-role')),
    'x-mode': modeForApi(request.headers.get('x-mode')),
  };
}

async function proxyResponse(response: Response): Promise<NextResponse> {
  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: { 'content-type': response.headers.get('content-type') ?? 'application/json' },
  });
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const config = apiConfig();
  if (config instanceof NextResponse) return config;

  const incoming = new URL(request.url);
  const resource = incoming.searchParams.get('resource') ?? '';
  if (!ALLOWED_RESOURCES.has(resource)) {
    return NextResponse.json({ error: { code: 'bad_request', message: 'Unknown dashboard resource' } }, { status: 400 });
  }

  const target = new URL(config.url);
  incoming.searchParams.forEach((value, key) => target.searchParams.set(key, value));

  const response = await fetch(target, {
    method: 'GET',
    headers: forwardHeaders(request, config.secret),
    cache: 'no-store',
  });
  return proxyResponse(response);
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const config = apiConfig();
  if (config instanceof NextResponse) return config;

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: { code: 'bad_json', message: 'Request body must be valid JSON' } }, { status: 400 });
  }

  const action = typeof body === 'object' && body !== null && !Array.isArray(body)
    ? (body as Record<string, unknown>).action
    : null;
  if (typeof action !== 'string' || !ALLOWED_ACTIONS.has(action)) {
    return NextResponse.json({ error: { code: 'bad_request', message: 'Unknown dashboard action' } }, { status: 400 });
  }

  const response = await fetch(config.url, {
    method: 'POST',
    headers: forwardHeaders(request, config.secret),
    body: JSON.stringify(body),
    cache: 'no-store',
  });
  return proxyResponse(response);
}
