import { useEffect, useState } from 'react';
import { api, type SyncStatus } from '../api';
import { syncText } from './syncText';

/**
 * «Última copia: Mac, hoy 22:30 · versión 3», debajo de «¿Quién entra?». Sirve para notar si
 * al cambiar de equipo todavía no ha llegado lo último (DISENO §15, riesgo aceptado).
 * Si la consulta falla, no se enseña nada: no impide entrar.
 */
export function SyncInfo() {
  const [status, setStatus] = useState<SyncStatus | null>(null);

  useEffect(() => {
    api
      .syncStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  if (!status) return null;
  return (
    <p className={status.cloud_available ? 'muted' : 'err'} style={{ fontSize: 13, margin: 0 }}>
      {syncText(status)}
    </p>
  );
}
