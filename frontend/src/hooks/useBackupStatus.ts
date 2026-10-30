import { useCallback, useEffect, useState } from 'react';
import { api, type BackupStatus } from '../api';
import { onBackupChanged, onDataChanged } from '../events';

// Cada cuánto se vuelve a preguntar: el backup periódico, el de arranque o un pendrive
// desconectado pueden cambiar el estado sin que el usuario haga nada
const REFRESH_MS = 60_000;
// Tras importar, el backup se hace en segundo plano: se mira de nuevo al cabo de un rato
const AFTER_CHANGE_MS = 5_000;

/** Estado de los backups. Se actualiza solo; `reload` lo fuerza. Si falla, queda en null
 * (el indicador simplemente no se muestra: no es imprescindible). */
export function useBackupStatus(): { status: BackupStatus | null; reload: () => void } {
  const [status, setStatus] = useState<BackupStatus | null>(null);
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    api
      .backupStatus()
      .then((s) => alive && setStatus(s))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [tick]);

  useEffect(() => {
    const timers: number[] = [];
    const interval = window.setInterval(reload, REFRESH_MS);
    const offData = onDataChanged(() => timers.push(window.setTimeout(reload, AFTER_CHANGE_MS)));
    const offBackup = onBackupChanged(reload);
    return () => {
      window.clearInterval(interval);
      timers.forEach((t) => window.clearTimeout(t));
      offData();
      offBackup();
    };
  }, [reload]);

  return { status, reload };
}
