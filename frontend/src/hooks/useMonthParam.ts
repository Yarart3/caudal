import { useCallback } from 'react';
import { useSearchParams } from 'react-router';

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;

/**
 * Mes elegido, guardado en la URL (`?mes=2026-09`) para que se pueda recargar o compartir.
 * Sin parámetro (o con uno que no vale) devuelve undefined: la API usa el mes del último movimiento.
 */
export function useMonthParam(): [string | undefined, (month: string) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get('mes');
  const month = raw !== null && MONTH.test(raw) ? raw : undefined;

  const setMonth = useCallback(
    (next: string) => {
      setParams(
        (previous) => {
          const copy = new URLSearchParams(previous);
          copy.set('mes', next);
          return copy;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  return [month, setMonth];
}
