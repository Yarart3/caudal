import { useEffect, useState } from 'react';
import { Navigate } from 'react-router';
import { api, errorMessage } from '../api';
import { useAuth } from '../auth/AuthContext';
import { Loading, Screen } from './Screen';

/**
 * Punto de entrada ("/"): decide a qué pantalla ir.
 * - Sin usuarios → asistente de primer arranque.
 * - Con sesión → panel.  - Sin sesión → "¿Quién entra?".
 */
export function StartPage() {
  const { user } = useAuth();
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .setupStatus()
      .then((status) => setNeedsSetup(status.needs_setup))
      .catch((err: unknown) => setError(errorMessage(err)));
  }, []);

  if (error !== null) {
    return (
      <Screen>
        <p className="error">{error}</p>
      </Screen>
    );
  }
  if (needsSetup === null || user === undefined) return <Loading />;
  if (needsSetup) return <Navigate to="/bienvenida" replace />;
  return <Navigate to={user ? '/panel' : '/entrar'} replace />;
}
