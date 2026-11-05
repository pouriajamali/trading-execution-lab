export type Command = Readonly<{ key: string; orderId: string; quantity: number }>;
export type Decision = { accepted: boolean; reason: string; sequence: number; exposure: number; replayed: boolean };
export type Snapshot = {
  sequence: number; position: number; pending: number; exposure: number; limit: number;
  reconciled: boolean; stopped: boolean;
  orders: { id: string; remaining: number; cancelRequested: boolean }[];
};
export type Session = { token: string };

function object(value: unknown, keys: string[]): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value) ||
      Object.keys(value).length !== keys.length || !keys.every(key => Object.hasOwn(value, key)))
    throw new Error('Invalid API object.');
  return value as Record<string, unknown>;
}
function integer(value: unknown, minimum = 0): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum)
    throw new Error('Invalid API integer.');
  return value;
}
function boolean(value: unknown): boolean {
  if (typeof value !== 'boolean') throw new Error('Invalid API boolean.');
  return value;
}
function sum(left: number, right: number): number {
  if (left > Number.MAX_SAFE_INTEGER - right) throw new Error('API sum is outside the display range.');
  return left + right;
}
export function parseSession(value: unknown): Session {
  const v = object(value, ['token']);
  if (typeof v.token !== 'string' || v.token.length < 16 || v.token.length > 8192 ||
      !/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{43}$/.test(v.token))
    throw new Error('Invalid API session.');
  // Syntax only. The backend verifies signature/claims when this token is used.
  return { token: v.token };
}
export function parseSnapshot(value: unknown): Snapshot {
  const v = object(value, ['sequence', 'position', 'pending', 'exposure', 'limit', 'reconciled', 'stopped', 'orders']);
  const sequence = integer(v.sequence), position = integer(v.position), pending = integer(v.pending);
  const exposure = integer(v.exposure), limit = integer(v.limit);
  const reconciled = boolean(v.reconciled), stopped = boolean(v.stopped);
  // Explicit bounded display profile; all API-created working IDs are <=64 UTF16
  // code units. C# Int64 beyond JS safe integers is rejected, never rounded.
  if (limit !== 10 || !Array.isArray(v.orders) || v.orders.length > 10_000)
    throw new Error('Unsupported API state.');
  const ids = new Set<string>();
  let outstanding = 0;
  const orders = v.orders.map(value => {
    const order = object(value, ['id', 'remaining', 'cancelRequested']);
    if (typeof order.id !== 'string' || !order.id.trim() || order.id.length > 64 || ids.has(order.id))
      throw new Error('Invalid or duplicate API order.');
    ids.add(order.id);
    const remaining = integer(order.remaining, 1);
    outstanding = sum(outstanding, remaining);
    return { id: order.id, remaining, cancelRequested: boolean(order.cancelRequested) };
  });
  if (pending !== outstanding || exposure !== sum(position, pending) || (!stopped && (!reconciled || exposure > limit)))
    throw new Error('Inconsistent API state.');
  return { sequence, position, pending, exposure, limit, reconciled, stopped, orders };
}
export function parseDecision(value: unknown): Decision {
  const v = object(value, ['accepted', 'reason', 'sequence', 'exposure', 'replayed']);
  const accepted = boolean(v.accepted), replayed = boolean(v.replayed);
  const sequence = integer(v.sequence), exposure = integer(v.exposure);
  const denials = ['Not ready', 'Invalid or reused order ID', 'Exposure limit', 'Quantity overflow: reconcile'];
  if (typeof v.reason !== 'string' || (accepted ? v.reason !== 'Applied' || exposure > 10 : !denials.includes(v.reason)))
    throw new Error('Unknown or inconsistent API receipt.');
  return { accepted, reason: v.reason, sequence, exposure, replayed };
}

export function commandFrom(key: string, id: string, quantity: string): Command {
  const orderId = id.trim();
  const amount = Number(quantity);
  if (!orderId || orderId.length > 64 || !/^\d+$/.test(quantity) || !Number.isSafeInteger(amount) || amount < 1)
    throw new Error('Enter an order ID of 1–64 characters and a whole quantity greater than zero.');
  return { key, orderId, quantity: amount };
}

export function requestFor(command: Command): RequestInit {
  return {
    method: 'POST',
    headers: { 'Idempotency-Key': command.key },
    body: JSON.stringify({ orderId: command.orderId, quantity: command.quantity })
  };
}

export class HttpError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function boundedJson(response: Response): Promise<unknown> {
  if (response.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase() !== 'application/json' || !response.body)
    throw new Error('Unexpected API content type.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let bytes = 0, text = '';
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      bytes += chunk.value.byteLength;
      if (bytes > 1_048_576) {
        await reader.cancel();
        throw new Error('API response limit exceeded.');
      }
      text += decoder.decode(chunk.value, { stream: true });
    }
    text += decoder.decode();
    return JSON.parse(text) as unknown;
  } finally { reader.releaseLock(); }
}

export function call(path: '/panel/api/session', token?: string, init?: RequestInit): Promise<Session>;
export function call(path: '/panel/api/state', token?: string, init?: RequestInit): Promise<Snapshot>;
export function call(path: '/reservations', token?: string, init?: RequestInit): Promise<Decision>;
export async function call(path: '/panel/api/session' | '/panel/api/state' | '/reservations', token?: string, init: RequestInit = {}): Promise<Session | Snapshot | Decision> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', 'Bearer ' + token);
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers, cache: 'no-store', signal: AbortSignal.timeout(8_000) });
  } catch {
    throw new Error('The local API did not respond. If a reservation was sent, retry that exact request to check its receipt.');
  }
  if (!response.ok) {
    const message: Record<number, string> = {
      400: 'The API rejected this request as invalid.',
      401: 'Access was rejected. Check the operator code or sign in again.',
      403: 'The operator role is required.',
      409: 'This idempotency key is already bound to different content.',
      429: 'Too many sign-in attempts. Try again in a minute.'
    };
    throw new HttpError(response.status, message[response.status] ?? `The local API returned HTTP ${response.status}.`);
  }
  try {
    const value = await boundedJson(response);
    if (path === '/panel/api/session') return parseSession(value);
    if (path === '/panel/api/state') return parseSnapshot(value);
    return parseDecision(value);
  } catch {
    // Do not render response bytes or parser messages, and do not infer rollback.
    throw new Error('The API response could not be verified. Replay the exact reservation to check its receipt.');
  }
}
