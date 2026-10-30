import { type BackupStatus } from '../api';
import { daysSince, formatMoment } from '../format';

/** Texto del último backup: «Último backup: hoy 18:42», o «hace 9 días» si es antiguo. */
export function lastBackupText(status: BackupStatus): string {
  if (!status.last_backup_at) return 'Todavía no hay ninguna copia';
  const when = formatMoment(status.last_backup_at);
  if (!status.stale) return `Último backup: ${when}`;
  return `Último backup hace ${daysSince(status.last_backup_at)} días (${when})`;
}
