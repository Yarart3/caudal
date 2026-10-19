import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, type Me } from '../api';
import { AuthContext } from './AuthContext';

/** Guarda quién ha entrado. Al abrir la app pregunta a /api/auth/me si ya había sesión. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null | undefined>(undefined);

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(() => ({ user, setUser, logout }), [user, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
