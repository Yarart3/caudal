import { type SyncStatus } from '../api';
import { formatMoment } from '../format';

const DEVICE_NAMES: Record<string, string> = { mac: 'Mac', pc: 'PC' };

export function deviceName(device: string): string {
  return DEVICE_NAMES[device] ?? device;
}

/** «Última copia: Mac, hoy 22:30 · versión 3» (Fase R). */
export function syncText(status: SyncStatus, now: Date = new Date()): string {
  if (!status.cloud_available) return 'No se ve la carpeta de Google Drive';
  const last = status.last_copy;
  if (!last) return 'Todavía no hay ninguna copia sincronizada';
  const when = formatMoment(last.at, now);
  return `Última copia: ${deviceName(last.device)}, ${when} · versión ${last.version}`;
}
