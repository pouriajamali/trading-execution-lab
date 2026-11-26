import type { Command } from './protocol';

export const pendingKey = 'execution-lab.pending-reservation.v1';
export type Pending = Readonly<{ instance: string; command: Command }>;
type StorageAccess = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
type Recovery = { pending?: Pending; blocked?: string };
const tabStorage = () => globalThis.sessionStorage;

export function loadRecovery(storage = tabStorage): Recovery {
  try {
    const raw = storage().getItem(pendingKey);
    if (raw === null) return {};
    if (raw.length > 768) throw new Error();
    const record = JSON.parse(raw);
    const command = record?.command;
    if (Object.keys(record).length !== 2 ||
        typeof record.instance !== 'string' || !/^[0-9a-f]{32}$/.test(record.instance) ||
        !command || Object.keys(command).length !== 3 ||
        typeof command.key !== 'string' || !/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(command.key) ||
        typeof command.orderId !== 'string' || !command.orderId || command.orderId.length > 64 ||
        command.orderId.trim() !== command.orderId ||
        !Number.isSafeInteger(command.quantity) || command.quantity < 1)
      throw new Error();
    return { pending: { instance: record.instance, command: {
      key: command.key, orderId: command.orderId, quantity: command.quantity,
    } } };
  } catch {
    return { blocked: 'Tab recovery storage could not be read. Reservations are disabled in this tab.' };
  }
}

export function savePending(pending: Pending, storage: StorageAccess = tabStorage()) {
  // Persist the exact request before the API can receive it.
  storage.setItem(pendingKey, JSON.stringify(pending));
}

export function clearPending(storage: StorageAccess = tabStorage()) {
  storage.removeItem(pendingKey);
}
