import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { api, setSessionExpiredHandler, type Me } from '../api';
import { AuthContext } from './AuthContext';

/** Guarda quién ha entrado. Al abrir la app pregunta a /api/auth/me si ya había sesión. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<Me | null | undefined>(undefined);
  const [expired, setExpired] = useState(false);

  const setUser = useCallback((next: Me | null) => {
    setUserState(next);
    if (next) setExpired(false);
  }, []);

  useEffect(() => {
    api
      .me()
      .then(setUserState)
      .catch(() => setUserState(null));
  }, []);

  // Cualquier 401 de la API con alguien dentro = la sesión ha caducado
  const userRef = useRef(user);
  useEffect(() => {
    userRef.current = user;
  }, [user]);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      if (userRef.current) {
        setExpired(true);
        setUserState(null);
      }
    });
    return () => setSessionExpiredHandler(null);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUserState(null);
      setExpired(false);
    }
  }, []);

  const checkSession = useCallback(() => {
    // Si ha caducado, la API da 401 y el aviso de arriba hace el resto
    api.me().catch(() => undefined);
  }, []);

  const value = useMemo(
    () => ({ user, expired, setUser, logout, checkSession }),
    [user, expired, setUser, logout, checkSession],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
