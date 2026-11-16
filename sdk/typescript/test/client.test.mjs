import assert from 'node:assert/strict';
import test from 'node:test';

import { UCVEVoiceClient } from '../dist/index.js';

class FakeWebSocket {
  static OPEN = 1;
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = FakeWebSocket.OPEN;
    this.sent = [];
    FakeWebSocket.instances.push(this);
  }

  send(value) {
    this.sent.push(value);
  }

  close(code = 1000, reason = '') {
    this.readyState = 3;
    this.closeArgs = { code, reason };
  }

  emitJson(value) {
    this.onmessage?.({ data: JSON.stringify(value) });
  }
}

globalThis.WebSocket = FakeWebSocket;

test('handshake encodes URL, resolves on ready, and answers keepalive', async () => {
  FakeWebSocket.instances.length = 0;
  const client = new UCVEVoiceClient('token +/?&=', {
    wsUrl: 'ws://localhost/ws/audio?existing=1',
    maxConnectAttempts: 1,
  });
  const connecting = client.connect();
  const socket = FakeWebSocket.instances[0];
  socket.onopen();

  const url = new URL(socket.url);
  assert.equal(url.searchParams.get('token'), 'token +/?&=');
  assert.equal(url.searchParams.get('existing'), '1');
  const hello = JSON.parse(socket.sent[0]);
  assert.equal(hello.event_type, 'protocol.hello');
  assert.equal(hello.sequence, 1);

  socket.emitJson({ event_type: 'session.ready', payload: { protocol_version: '1.0.0' } });
  await connecting;
  socket.emitJson({ event_type: 'control.ping', payload: {} });
  await Promise.resolve();
  assert.equal(JSON.parse(socket.sent.at(-1)).event_type, 'control.pong');
  client.disconnect();
});

test('production client rejects unapproved provider overrides', () => {
  assert.throws(
    () => new UCVEVoiceClient('token', { demoProviderOverrides: { llm_provider: 'groq' } }),
    /demo-only/,
  );
});

test('remote close and token expiry are surfaced to host callbacks', async () => {
  FakeWebSocket.instances.length = 0;
  const received = [];
  const client = new UCVEVoiceClient('token', {
    maxConnectAttempts: 1,
    onTokenExpiring: (payload) => received.push(['expiry', payload]),
    onClose: (payload) => received.push(['close', payload]),
  });
  const connecting = client.connect();
  const socket = FakeWebSocket.instances[0];
  socket.onopen();
  socket.emitJson({ event_type: 'session.ready', payload: { protocol_version: '1.0.0' } });
  await connecting;
  socket.emitJson({ event_type: 'session.token_expiring', payload: { expires_at_ms: 10 } });
  socket.emitJson({ event_type: 'session.close', payload: { code: 'DONE', retryable: false } });
  await Promise.resolve();
  assert.deepEqual(received.map(([kind]) => kind), ['expiry', 'close']);
});

test('audio lifecycle events expose the turn needed for playback acknowledgements', async () => {
  FakeWebSocket.instances.length = 0;
  const received = [];
  const client = new UCVEVoiceClient('token', {
    maxConnectAttempts: 1,
    onAudioStart: (payload) => received.push(['start', payload.turn_id]),
    onAudioEnd: (payload) => received.push(['end', payload.turn_id]),
  });
  const connecting = client.connect();
  const socket = FakeWebSocket.instances[0];
  socket.onopen();
  socket.emitJson({ event_type: 'session.ready', payload: { protocol_version: '1.0.0' } });
  await connecting;
  socket.emitJson({ event_type: 'audio.start', payload: { turn_id: 'turn-1', server_send_ms: 1 } });
  socket.emitJson({ event_type: 'audio.end', payload: { turn_id: 'turn-1' } });
  await Promise.resolve();
  assert.deepEqual(received, [['start', 'turn-1'], ['end', 'turn-1']]);
  client.disconnect();
});

test('a session rejected after the socket opens is not retried with the spent token', async () => {
  FakeWebSocket.instances.length = 0;
  const { SessionRejectedError } = await import('../dist/index.js');
  const client = new UCVEVoiceClient('token', {
    wsUrl: 'ws://localhost/ws/audio',
    maxConnectAttempts: 3,
    reconnectBackoffMs: 0,
  });
  const connecting = client.connect();
  const socket = FakeWebSocket.instances[0];
  socket.onopen();
  socket.onclose?.({ code: 4401, reason: 'invalid session' });

  await assert.rejects(connecting, (error) => {
    assert.ok(error instanceof SessionRejectedError);
    assert.equal(error.code, 4401);
    assert.equal(error.reason, 'invalid session');
    return true;
  });
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.equal(FakeWebSocket.instances.length, 1);
});

test('an unreachable worker is retried before giving up', async () => {
  FakeWebSocket.instances.length = 0;
  const client = new UCVEVoiceClient('token', {
    wsUrl: 'ws://localhost/ws/audio',
    maxConnectAttempts: 2,
    reconnectBackoffMs: 0,
  });
  const connecting = client.connect();
  FakeWebSocket.instances[0].onerror?.();
  await new Promise((resolve) => setTimeout(resolve, 5));
  const second = FakeWebSocket.instances[1];
  assert.ok(second, 'expected a second attempt');
  second.onopen();
  second.emitJson({ event_type: 'session.ready', payload: { protocol_version: '1.0.0' } });
  await connecting;
  client.disconnect();
});
