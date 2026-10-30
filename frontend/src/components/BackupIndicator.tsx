import { useBackupStatus } from '../hooks/useBackupStatus';
import { lastBackupText } from './backupText';

/** «Último backup: hoy 18:42 · Pendrive ✓ · OneDrive ✓», debajo del título (maqueta).
 * En rojo lo que necesita atención: sin contraseña, copia antigua o un destino con ✗. */
export function BackupIndicator() {
  const { status } = useBackupStatus();
  if (!status) return null;

  if (!status.configured) {
    return (
      <span className="backup-line">
        <span className="backup-bad">
          Las copias de seguridad están desactivadas: falta la contraseña de backup
        </span>
      </span>
    );
  }

  return (
    <span className="backup-line">
      <span className={status.stale ? 'backup-bad' : undefined}>{lastBackupText(status)}</span>
      {status.destinations.map((d) => (
        <span
          key={d.destination}
          className={d.ok ? undefined : 'backup-bad'}
          title={d.message ?? undefined}
        >
          {' · '}
          {d.label} {d.ok ? '✓' : '✗'}
          <span className="sr-only">
            {d.ok ? ' correcto' : ` con problemas: ${d.message ?? ''}`}
          </span>
        </span>
      ))}
    </span>
  );
}
