import assert from 'node:assert/strict';
import test from 'node:test';
import { commandFrom, requestFor } from './protocol.ts';

test('retry preserves the exact request and idempotency key', () => {
  const command = commandFrom('same-key', ' sample ', '2');
  assert.deepEqual(requestFor(command), requestFor(command));
  assert.equal(requestFor(command).headers['Idempotency-Key'], 'same-key');
  assert.deepEqual(JSON.parse(requestFor(command).body), { orderId: 'sample', quantity: 2 });
});

test('invalid quantities and identifiers cannot become commands', () => {
  for (const invalid of ['0', '-1', '1.5', '1e2', '', '9007199254740993'])
    assert.throws(() => commandFrom('key', 'sample', invalid));
  assert.throws(() => commandFrom('key', ' ', '2'));
  assert.throws(() => commandFrom('key', 'a'.repeat(65), '2'));
});
