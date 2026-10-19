import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router';
import { api, ApiError, errorMessage, type UserCard } from '../api';
import { useAuth } from '../auth/AuthContext';
import { Loading, Screen } from './Screen';

const FOOT =
  'Tras 5 intentos fallidos el usuario se bloquea 5 minutos. La sesión se cierra sola tras 30 minutos sin usarla.';

/** "¿Quién entra?": se elige la tarjeta del usuario y después se escribe la contraseña. */
export function LoginPage() {
  const { user, expired } = useAuth();
  const [users, setUsers] = useState<UserCard[] | null>(null);
  const [picked, setPicked] = useState<UserCard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .users()
      .then(setUsers)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, []);

  // Si ya hay sesión, a qué esperar: directo al panel
  if (user) return <Navigate to="/panel" replace />;
  if (users === null && error === null) return <Loading />;
  // Sin usuarios todavía: primero el asistente
  if (users !== null && users.length === 0) return <Navigate to="/" replace />;

  if (picked) {
    return <PasswordStep user={picked} onBack={() => setPicked(null)} />;
  }

  return (
    <Screen foot={FOOT}>
      <h1 style={{ fontSize: 26 }}>¿Quién entra?</h1>
      {expired && (
        <p className="note" role="status">
          Tu sesión se ha cerrado tras 30 minutos sin usarla. Vuelve a entrar.
        </p>
      )}
      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      {users?.map((u) => (
        <button key={u.username} type="button" className="user-btn" onClick={() => setPicked(u)}>
          <span className="avatar" style={{ background: u.color }} aria-hidden="true">
            {u.initial}
          </span>
          <strong style={{ fontSize: 17 }}>{u.display_name}</strong>
        </button>
      ))}
    </Screen>
  );
}

function PasswordStep({ user, onBack }: { user: UserCard; onBack: () => void }) {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => input.current?.focus(), []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (password === '') {
      setError('Escribe la contraseña');
      return;
    }
    setSending(true);
    setError(null);
    try {
      const me = await api.login(user.username, password);
      setUser(me);
      navigate('/panel', { replace: true });
    } catch (err) {
      // 401: contraseña incorrecta · 429: bloqueado. El mensaje ya viene en castellano.
      setError(errorMessage(err));
      if (err instanceof ApiError && err.status === 401) setPassword('');
      setSending(false);
      input.current?.focus();
    }
  }

  return (
    <Screen foot={FOOT}>
      <div className="row">
        <span className="avatar" style={{ background: user.color }} aria-hidden="true">
          {user.initial}
        </span>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <strong style={{ fontSize: 18 }}>Hola, {user.display_name}</strong>
          <span className="muted" style={{ fontSize: 13 }}>
            Introduce tu contraseña
          </span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="login-body" noValidate>
        {/* El nombre de usuario oculto ayuda al gestor de contraseñas del navegador */}
        <input
          type="text"
          name="username"
          autoComplete="username"
          value={user.username}
          readOnly
          hidden
        />
        <div className="field">
          <label htmlFor="pwd">Contraseña</label>
          <input
            id="pwd"
            ref={input}
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error && (
          <span className="err" role="alert">
            {error}
          </span>
        )}
        <button type="submit" className="btn btn-primary" disabled={sending}>
          {sending ? 'Entrando…' : 'Entrar'}
        </button>
      </form>

      <button type="button" className="link-btn" onClick={onBack}>
        ← Cambiar de usuario
      </button>
    </Screen>
  );
}
