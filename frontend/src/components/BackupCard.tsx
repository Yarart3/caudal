import { useState } from 'react';
import { api, errorMessage, type BackupDestination } from '../api';
import { notifyBackupChanged } from '../events';
import { formatMoment } from '../format';
import { useBackupStatus } from '../hooks/useBackupStatus';
import { lastBackupText } from './backupText';

/** Ajustes → Copias de seguridad: estado de cada destino y «Hacer copia ahora». */
export function BackupCard() {
  const { status, reload } = useBackupStatus();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const result = await api.runBackup();
      if (result.ok) {
        const failed = result.status.destinations.filter((d) => !d.ok).map((d) => d.label);
        setMessage(
          failed.length === 0
            ? 'Copia hecha en el pendrive y en OneDrive.'
            : `Copia hecha, pero no en: ${failed.join(', ')}.`,
        );
      } else {
        setError('No se ha podido guardar la copia en ningún sitio.');
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
      reload();
      notifyBackupChanged();
    }
  }

  return (
    <div className="card panel">
      <div className="between" style={{ flexWrap: 'wrap', gap: 12 }}>
        <h2>Copias de seguridad</h2>
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleRun}
          disabled={busy || status?.configured === false}
        >
          {busy ? 'Haciendo copia…' : 'Hacer copia ahora'}
        </button>
      </div>

      {status === null ? (
        <p className="muted">Cargando…</p>
      ) : !status.configured ? (
        <p className="err">
          Falta la contraseña de backup (BACKUP_PASSWORD en el archivo .env). Sin ella no se hacen
          copias.
        </p>
      ) : (
        <>
          <p className={status.stale ? 'err' : 'muted'}>{lastBackupText(status)}</p>
          <ul className="backup-list">
            {status.destinations.map((d) => (
              <DestinationRow key={d.destination} destination={d} />
            ))}
          </ul>
          <p className="muted" style={{ fontSize: 13 }}>
            Se hacen solas tras importar, cada hora si hay cambios, al cerrar Caudal y al abrirlo si
            la última tiene más de {status.max_age_days} días. Se guardan las 30 últimas en cada
            sitio, cifradas con la contraseña de backup.
          </p>
        </>
      )}

      {message && (
        <p className="ok" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function DestinationRow({ destination: d }: { destination: BackupDestination }) {
  let detail: string;
  if (!d.available) detail = d.message ?? 'No disponible';
  else if (!d.last_at) detail = 'Todavía sin copias';
  else if (d.ok) detail = `Última copia: ${formatMoment(d.last_at)}`;
  else detail = `La última copia falló: ${d.message ?? 'error desconocido'}`;

  return (
    <li>
      <span className={`backup-mark ${d.ok ? 'good' : 'bad'}`} aria-hidden="true">
        {d.ok ? '✓' : '✗'}
      </span>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
        <strong>{d.label}</strong>
        <span className={d.ok ? 'muted' : 'err'} style={{ fontSize: 13 }}>
          {detail}
        </span>
        {!d.ok && d.available && d.last_ok_at && (
          <span className="muted" style={{ fontSize: 13 }}>
            Última copia buena: {formatMoment(d.last_ok_at)}
          </span>
        )}
        {!d.available && d.last_ok_at && (
          <span className="muted" style={{ fontSize: 13 }}>
            Última copia: {formatMoment(d.last_ok_at)}
          </span>
        )}
      </div>
    </li>
  );
}
