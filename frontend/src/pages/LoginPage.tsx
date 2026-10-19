import { useEffect, useState } from 'react';
import { api, errorMessage, type UserCard } from '../api';
import { Screen } from './Screen';

// Provisional (parte 3.1): lista los usuarios para comprobar que la API responde.
// "¿Quién entra?" y la contraseña de verdad llegan en la parte 3.3.
export function LoginPage() {
  const [users, setUsers] = useState<UserCard[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .users()
      .then(setUsers)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, []);

  return (
    <Screen>
      <h1>¿Quién entra?</h1>
      {error && <p className="error">{error}</p>}
      {users?.map((u) => (
        <div key={u.username} className="row">
          <span className="avatar" style={{ background: u.color }}>
            {u.initial}
          </span>
          {u.display_name}
        </div>
      ))}
      <p className="muted">El inicio de sesión llega en la parte 3.3.</p>
    </Screen>
  );
}
