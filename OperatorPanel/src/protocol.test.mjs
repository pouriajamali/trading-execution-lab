import assert from 'node:assert/strict';
import test from 'node:test';
import { call, commandFrom, HttpError, parseSession, parseSnapshot, parseDecision, requestFor } from './protocol.ts';

test('retry preserves the exact request and idempotency key', () => {
  const command = commandFrom('same-key', ' sample ', '2');
  assert.deepEqual(requestFor(command), requestFor(command));
  assert.equal(requestFor(command).headers['Idempotency-Key'], 'same-key');
  assert.deepEqual(JSON.parse(requestFor(command).body), { orderId: 'sample', quantity: 2 });
});

test('HTTP transport keeps token out of URL/body and requests no caching', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (path, init) => {
      assert.equal(path, '/reservations');
      assert.equal(init.headers.get('Authorization'), 'Bearer synthetic-test-token');
      assert.equal(init.headers.get('Content-Type'), 'application/json');
      assert.equal(init.headers.get('Idempotency-Key'), 'stable-key');
      assert.equal(init.cache, 'no-store');
      assert.ok(init.signal instanceof AbortSignal);
      assert.ok(!init.body.includes('synthetic-test-token'));
      return Response.json({ accepted: true, reason: 'Applied', sequence: 3, exposure: 9, replayed: false });
    };
    assert.deepEqual(await call('/reservations', 'synthetic-test-token', requestFor(commandFrom('stable-key', 'a', '2'))),
      { accepted: true, reason: 'Applied', sequence: 3, exposure: 9, replayed: false });
  } finally { globalThis.fetch = original; }
});

test('session parser rejects incomplete, extra, non-string and unbounded token DTOs', () => {
  const session = { token: 'e30.e30.' + 'a'.repeat(43) };
  assert.deepEqual(parseSession(session), session);
  for (const invalid of [{}, null, [], { token: 1 }, { token: 'a.b.c' }, { token: 'a'.repeat(8193) },
    { ...session, private: 'must-not-be-rendered' }]) assert.throws(() => parseSession(invalid));
});

const snapshot = { sequence: 2, position: 4, pending: 3, exposure: 7, limit: 10,
  reconciled: true, stopped: false, orders: [{ id: 'working', remaining: 3, cancelRequested: false }] };
test('state parser verifies closed shape, real wire types, unique IDs and exact safe exposure', () => {
  assert.deepEqual(parseSnapshot(snapshot), snapshot);
  const invalids = [null, {}, { ...snapshot, sequence: 9007199254740992 }, { ...snapshot, position: -1 },
    { ...snapshot, pending: '3' }, { ...snapshot, stopped: 'false' }, { ...snapshot, limit: 11 },
    { ...snapshot, orders: [snapshot.orders[0], snapshot.orders[0]], pending: 6, exposure: 10 },
    { ...snapshot, orders: [{ ...snapshot.orders[0], id: 'a'.repeat(65) }] },
    { ...snapshot, orders: [{ ...snapshot.orders[0], remaining: 0 }] },
    { ...snapshot, exposure: 8 }, { ...snapshot, reconciled: false },
    { ...snapshot, position: Number.MAX_SAFE_INTEGER, exposure: Number.MAX_SAFE_INTEGER },
    { ...snapshot, orders: Array(10001).fill(snapshot.orders[0]) }, { ...snapshot, extra: true }];
  for (const invalid of invalids) assert.throws(() => parseSnapshot(invalid));
  // A halted, valid over-limit authoritative snapshot is representable, not Ready.
  assert.equal(parseSnapshot({ ...snapshot, position: 11, exposure: 14, stopped: true }).exposure, 14);
});

test('receipt parser rejects partial, unsafe, unknown or contradictory decisions', () => {
  const receipt = { accepted: true, reason: 'Applied', sequence: 3, exposure: 9, replayed: false };
  assert.deepEqual(parseDecision(receipt), receipt);
  for (const invalid of [{ accepted: true }, { ...receipt, replayed: 'false' }, { ...receipt, reason: 'new-private-reason' },
    { ...receipt, accepted: false }, { ...receipt, exposure: 11 }, { ...receipt, sequence: 9007199254740992 },
    { ...receipt, extra: 'private' }]) assert.throws(() => parseDecision(invalid));
});

test('valid JSON with malformed DTO is an unknown response, never a verified receipt', async () => {
  const original = globalThis.fetch;
  const command = commandFrom('same-key-after-commit', 'a', '2');
  try {
    for (const [path, body] of [['/panel/api/session', { token: 'private-malformed-token' }],
      ['/panel/api/state', { ...snapshot, exposure: 8 }], ['/reservations', { accepted: true }]]) {
      globalThis.fetch = async () => Response.json(body);
      await assert.rejects(call(path), problem => /could not be verified/.test(problem.message) &&
        !problem.message.includes('private-malformed-token'));
    }
    assert.equal(requestFor(command).headers['Idempotency-Key'], 'same-key-after-commit');
  } finally { globalThis.fetch = original; }
});

test('actual streamed response bytes are capped before JSON/schema adoption', async () => {
  const original = globalThis.fetch;
  let cancelled = false;
  try {
    globalThis.fetch = async () => new Response(new ReadableStream({
      start(controller) { controller.enqueue(new Uint8Array(1_048_577)); },
      cancel() { cancelled = true; }
    }), { headers: { 'Content-Type': 'application/json' } });
    await assert.rejects(call('/panel/api/state'), /could not be verified/);
    assert.equal(cancelled, true);
  } finally { globalThis.fetch = original; }
});

test('lost responses are unknown results and retain the exact original command', async () => {
  const original = globalThis.fetch;
  const command = commandFrom('stable-key', 'a', '2');
  const request = requestFor(command);
  try {
    globalThis.fetch = async () => { throw new Error('private transport details'); };
    await assert.rejects(call('/reservations', 'test-token', request), problem =>
      /retry that exact request/.test(problem.message) && !problem.message.includes('private'));
    assert.deepEqual(requestFor(command), request);
  } finally { globalThis.fetch = original; }
});

test('HTTP conflicts and expired credentials preserve status without exposing response bytes', async () => {
  const original = globalThis.fetch;
  try {
    for (const status of [400, 401, 403, 409, 429, 500]) {
      globalThis.fetch = async () => new Response('private-response-test-marker', { status });
      await assert.rejects(call('/reservations'), problem => problem instanceof HttpError &&
        problem.status === status && !problem.message.includes('private-response-test-marker'));
    }
  } finally { globalThis.fetch = original; }
});

test('unreadable success response does not imply rollback or expose parser bytes', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response('private-parser-test-marker', { status: 200 });
    await assert.rejects(call('/reservations'), problem => /Replay the exact reservation/.test(problem.message) &&
      !problem.message.includes('private-parser-test-marker'));
  } finally { globalThis.fetch = original; }
});

test('invalid quantities and identifiers cannot become commands', () => {
  for (const invalid of ['0', '-1', '1.5', '1e2', '', '9007199254740993'])
    assert.throws(() => commandFrom('key', 'sample', invalid));
  assert.throws(() => commandFrom('key', ' ', '2'));
  assert.throws(() => commandFrom('key', 'a'.repeat(65), '2'));
});
