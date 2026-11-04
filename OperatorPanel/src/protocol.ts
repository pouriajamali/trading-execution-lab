export type Command = Readonly<{ key: string; orderId: string; quantity: number }>;
export type Decision = { accepted: boolean; reason: string; sequence: number; exposure: number; replayed: boolean };
export type Snapshot = {
  sequence: number; position: number; pending: number; exposure: number; limit: number;
  reconciled: boolean; stopped: boolean;
  orders: { id: string; remaining: number; cancelRequested: boolean }[];
};

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

export async function call<T>(path: string, token?: string, init: RequestInit = {}): Promise<T> {
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
  return response.json() as Promise<T>;
}
