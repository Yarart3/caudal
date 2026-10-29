import { useEffect, useState } from 'react';

/** El valor, pero solo cuando lleva `ms` milisegundos sin cambiar (para el buscador). */
export function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}
