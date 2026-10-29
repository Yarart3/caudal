import { useEffect, useState } from 'react';
import { api, errorMessage, type Account, type Category } from '../api';
import { onDataChanged } from '../events';

export type Lookups = { accounts: Account[]; categories: Category[] };

/** Cuentas y categorías del usuario (para los desplegables y para poner nombres en la
 * tabla). Se recargan solas cuando cambian los datos. */
export function useLookups(): { lookups: Lookups | null; error: string | null } {
  const [lookups, setLookups] = useState<Lookups | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => {
      Promise.all([api.accounts(), api.categories()])
        .then(([accounts, categories]) => alive && setLookups({ accounts, categories }))
        .catch((err: unknown) => alive && setError(errorMessage(err)));
    };
    load();
    const off = onDataChanged(load);
    return () => {
      alive = false;
      off();
    };
  }, []);

  return { lookups, error };
}
