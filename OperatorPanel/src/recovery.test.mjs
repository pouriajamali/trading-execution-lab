import assert from 'node:assert/strict';
import test from 'node:test';
import { call, instanceHeader, requestFor } from './protocol.ts';
import { clearPending, loadRecovery, pendingKey, savePending } from './recovery.ts';

const instance = 'ab'.repeat(16);
const command = { key: 'eea4bd7a-5a88-4906-8a2f-5d309fba6a1a', orderId: 'sample', quantity: 2 };

test('tab reload restores the exact request and process binding until receipt is known', () => {
  const values = new Map();
  const storage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
  savePending({ instance, command }, storage);
  const pending = loadRecovery(() => storage).pending;
  assert.deepEqual(requestFor(pending.command, pending.instance), requestFor(command, instance));
  assert.equal(requestFor(pending.command, pending.instance).headers[instanceHeader], instance);
  assert.deepEqual(Object.keys(JSON.parse(values.get(pendingKey))).sort(), ['command', 'instance']);
  clearPending(storage);
  assert.deepEqual(loadRecovery(() => storage), {});
});

test('unavailable or malformed tab recovery fails closed', () => {
  for (const raw of ['null', '{', 'x'.repeat(769), JSON.stringify({ instance, command: {
    ...command, key: 'new request', quantity: 0,
  } })]) {
    const recovered = loadRecovery(() => ({ getItem: () => raw }));
    assert.ok(recovered.blocked);
    assert.equal(recovered.pending, undefined);
  }
  assert.ok(loadRecovery(() => { throw new Error('storage denied'); }).blocked);
});

test('login accepts a process binding only after verifying the session response', async () => {
  const fetch = globalThis.fetch;
  const token = 'e30.e30.' + 'a'.repeat(43);
  try {
    globalThis.fetch = async () => Response.json({ token }, { headers: { [instanceHeader]: instance } });
    assert.deepEqual(await call('/panel/api/session'), { token, instance });
    globalThis.fetch = async () => Response.json({ token });
    await assert.rejects(call('/panel/api/session'), /could not be verified/);
  } finally { globalThis.fetch = fetch; }
});
