import { useEffect, useState } from 'react';
import { errorMessage } from '../api';
import { onDataChanged } from '../events';

/**
 * Datos de un panel (`api.netWorth`, `api.cashflow`…) para un mes ("AAAA-MM"; sin él, el del
 * último movimiento). Se vuelven a pedir si cambia el mes o los datos (importar, editar…).
 *
 * `load` tiene que ser una función estable (definida fuera del componente): si fuera nueva en
 * cada render, el efecto se repetiría sin parar.
 */
export function useDashboard<T>(
  load: (month?: string) => Promise<T>,
  month?: string,
): { data: T | null; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let alive = true;
    load(month)
      .then((result) => {
        if (!alive) return;
        setData(result);
        setError(null);
      })
      .catch((err: unknown) => alive && setError(errorMessage(err)));
    return () => {
      alive = false;
    };
  }, [load, month, reload]);

  useEffect(() => onDataChanged(() => setReload((n) => n + 1)), []);

  return { data, error };
}
