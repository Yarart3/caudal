import { createContext, useContext } from 'react';
import type { Me } from '../api';

export type AuthState = {
  /** undefined = aún comprobando la sesión · null = sin sesión · Me = usuario que ha entrado */
  user: Me | null | undefined;
  /** true si se ha vuelto a "¿Quién entra?" porque la sesión caducó */
  expired: boolean;
  setUser: (user: Me | null) => void;
  logout: () => Promise<void>;
  /** Pregunta al servidor si la sesión sigue viva (al volver a la pestaña) */
  checkSession: () => void;
};

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const auth = useContext(AuthContext);
  if (auth === null) throw new Error('useAuth se usa fuera de <AuthProvider>');
  return auth;
}
