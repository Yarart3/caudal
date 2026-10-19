import type { ReactNode } from 'react';
import { Navigate } from 'react-router';
import { Loading } from '../pages/Screen';
import { useAuth } from './AuthContext';

/** Protege una pantalla: sin sesión, manda a "¿Quién entra?". */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (user === undefined) return <Loading />;
  if (user === null) return <Navigate to="/entrar" replace />;
  return children;
}
