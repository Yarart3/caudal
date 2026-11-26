import { useEffect, useState, type CSSProperties, type FormEvent } from 'react';
import { api, errorMessage, type AdminUser } from '../api';
import { useAuth } from '../auth/AuthContext';

const NEW_COLOR = '#A05A35';
const MIN_PASSWORD = 8;

/** Ajustes → Usuarios (Fase 4). Solo la ve el administrador: crear, cambiar nombre y color,
 * hacer administrador, desactivar y poner una contraseña nueva. Nunca se borra a nadie. */
export function UsersCard() {
  const { user: me, setUser } = useAuth();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .adminUsers()
      .then((list) => alive && setUsers(list))
      .catch((err: unknown) => alive && setError(errorMessage(err)));
    return () => {
      alive = false;
    };
  }, [reload]);

  /** Ejecuta un cambio, recarga la lista y enseña el mensaje (o el error). */
  async function run(action: () => Promise<string>): Promise<boolean> {
    setError(null);
    setMessage(null);
    try {
      setMessage(await action());
      setReload((n) => n + 1);
      // Si he cambiado mi propio nombre o color, que se vea en la barra lateral
      api.me().then(setUser, () => undefined);
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    }
  }

  return (
    <section className="card panel">
      <h2>Usuarios</h2>
      <p className="muted" style={{ fontSize: 13, margin: 0 }}>
        Cada usuario solo ve sus propios datos. Un usuario desactivado no sale en «¿Quién entra?» ni
        puede entrar, pero sus datos se guardan y se puede volver a activar.
      </p>
      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="ok" role="status">
          {message}
        </p>
      )}
      {users === null ? (
        !error && <p className="muted">Cargando…</p>
      ) : (
        <ul className="edit-list">
          {users.map((u) => (
            <UserRow
              key={`${u.id}-${u.display_name}-${u.color}-${u.is_active}-${u.is_admin}`}
              user={u}
              isMe={u.username === me?.username}
              run={run}
              onOwnPasswordChanged={() => setUser(null)}
            />
          ))}
        </ul>
      )}
      <NewUserForm run={run} />
    </section>
  );
}

type Run = (action: () => Promise<string>) => Promise<boolean>;

function UserRow({
  user,
  isMe,
  run,
  onOwnPasswordChanged,
}: {
  user: AdminUser;
  isMe: boolean;
  run: Run;
  onOwnPasswordChanged: () => void;
}) {
  const [name, setName] = useState(user.display_name);
  const [color, setColor] = useState(user.color);
  const [resetting, setResetting] = useState(false);
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const dirty =
    name.trim() !== user.display_name || color.toLowerCase() !== user.color.toLowerCase();

  async function act(action: () => Promise<string>): Promise<boolean> {
    setBusy(true);
    const ok = await run(action);
    setBusy(false);
    return ok;
  }

  async function save() {
    if (name.trim() === '') return;
    await act(async () => {
      await api.updateUser(user.id, { display_name: name.trim(), color });
      return `Usuario «${user.username}» guardado`;
    });
  }

  async function toggleActive() {
    await act(async () => {
      await api.updateUser(user.id, { is_active: !user.is_active });
      return user.is_active
        ? `«${user.display_name}» desactivado. Sus datos se guardan.`
        : `«${user.display_name}» activado de nuevo`;
    });
  }

  async function toggleAdmin() {
    await act(async () => {
      await api.updateUser(user.id, { is_admin: !user.is_admin });
      return user.is_admin
        ? `«${user.display_name}» ya no es administrador`
        : `«${user.display_name}» ahora es administrador`;
    });
  }

  async function resetPassword(event: FormEvent) {
    event.preventDefault();
    if (password.length < MIN_PASSWORD) return;
    const ok = await act(async () => {
      await api.resetUserPassword(user.id, password);
      return `Contraseña de «${user.display_name}» cambiada. Si estaba bloqueado, ya puede entrar.`;
    });
    if (ok) {
      setPassword('');
      setResetting(false);
      // Cambiar la propia contraseña cierra también esta sesión: a «¿Quién entra?»
      if (isMe) onOwnPasswordChanged();
    }
  }

  const badges: { text: string; style: CSSProperties }[] = [];
  if (user.is_admin)
    badges.push({
      text: 'Administrador',
      style: { background: 'var(--purple-bg)', color: 'var(--purple)' },
    });
  if (!user.is_active)
    badges.push({
      text: 'Desactivado',
      style: { background: 'var(--soft)', color: 'var(--neutral)' },
    });
  if (user.locked)
    badges.push({
      text: 'Bloqueado',
      style: { background: 'var(--warn-bg)', color: 'var(--warn)' },
    });

  return (
    <li className="edit-row" style={user.is_active ? undefined : { opacity: 0.7 }}>
      <div className="row" style={{ flexWrap: 'wrap' }}>
        <span className="avatar" style={{ background: color }} aria-hidden="true">
          {(name.trim()[0] ?? user.initial).toUpperCase()}
        </span>
        <input
          type="color"
          className="swatch"
          aria-label={`Color de ${user.display_name}`}
          value={color}
          onChange={(e) => setColor(e.target.value)}
        />
        <input
          className="input"
          style={{ flex: '1 1 140px' }}
          type="text"
          maxLength={60}
          aria-label={`Nombre visible de ${user.display_name}`}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <span className="muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
          usuario: {user.username}
          {isMe && ' (tú)'}
        </span>
        {badges.map((b) => (
          <span key={b.text} className="badge" style={b.style}>
            {b.text}
          </span>
        ))}
        {dirty && (
          <button type="button" className="btn btn-sm btn-accent" onClick={save} disabled={busy}>
            Guardar
          </button>
        )}
      </div>
      <div className="row" style={{ flexWrap: 'wrap', gap: 12 }}>
        <button
          type="button"
          className="link-btn"
          onClick={() => setResetting((v) => !v)}
          disabled={busy}
        >
          {user.locked ? 'Contraseña nueva y desbloquear' : 'Contraseña nueva'}
        </button>
        {!isMe && (
          <>
            <button type="button" className="link-btn" onClick={toggleAdmin} disabled={busy}>
              {user.is_admin ? 'Quitar administrador' : 'Hacer administrador'}
            </button>
            <button
              type="button"
              className={`link-btn${user.is_active ? ' danger' : ''}`}
              onClick={toggleActive}
              disabled={busy}
            >
              {user.is_active ? 'Desactivar' : 'Activar'}
            </button>
          </>
        )}
      </div>
      {resetting && (
        <form className="ask" onSubmit={resetPassword} noValidate>
          <label htmlFor={`pw-${user.id}`}>
            Contraseña nueva para «{user.display_name}» (al menos {MIN_PASSWORD} caracteres).
            {isMe
              ? ' Se cerrará tu sesión y tendrás que entrar con la nueva.'
              : ' Se cerrarán sus sesiones abiertas.'}
          </label>
          <div className="row" style={{ flexWrap: 'wrap' }}>
            <input
              id={`pw-${user.id}`}
              className="input"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="submit"
              className="btn btn-sm btn-accent"
              disabled={busy || password.length < MIN_PASSWORD}
            >
              Cambiar
            </button>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => {
                setResetting(false);
                setPassword('');
              }}
              disabled={busy}
            >
              Cancelar
            </button>
          </div>
        </form>
      )}
    </li>
  );
}

function NewUserForm({ run }: { run: Run }) {
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [color, setColor] = useState(NEW_COLOR);
  const [password, setPassword] = useState('');
  const [isAdmin, setIsAdmin] = useState(false);
  const [busy, setBusy] = useState(false);
  const ready =
    username.trim().length >= 2 && displayName.trim() !== '' && password.length >= MIN_PASSWORD;

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!ready) return;
    setBusy(true);
    const ok = await run(async () => {
      const created = await api.createUser({
        username: username.trim(),
        display_name: displayName.trim(),
        color,
        password,
        is_admin: isAdmin,
      });
      return `Usuario «${created.username}» creado, con las categorías y reglas iniciales`;
    });
    setBusy(false);
    if (ok) {
      setUsername('');
      setDisplayName('');
      setPassword('');
      setIsAdmin(false);
      setColor(NEW_COLOR);
    }
  }

  return (
    <form className="add-form" onSubmit={handleCreate} noValidate>
      <h3 className="sub">Nuevo usuario</h3>
      <div className="row" style={{ flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <input
          type="color"
          className="swatch"
          aria-label="Color"
          value={color}
          onChange={(e) => setColor(e.target.value)}
        />
        <div className="field" style={{ flex: '1 1 140px' }}>
          <label htmlFor="usr-nombre">Nombre visible</label>
          <input
            id="usr-nombre"
            type="text"
            maxLength={60}
            placeholder="Ej. Abuela"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </div>
        <div className="field" style={{ flex: '1 1 120px' }}>
          <label htmlFor="usr-usuario">Usuario</label>
          <input
            id="usr-usuario"
            type="text"
            maxLength={40}
            autoCapitalize="none"
            placeholder="Ej. abuela"
            value={username}
            onChange={(e) => setUsername(e.target.value.toLowerCase())}
          />
        </div>
        <div className="field" style={{ flex: '1 1 140px' }}>
          <label htmlFor="usr-clave">Contraseña</label>
          <input
            id="usr-clave"
            type="password"
            autoComplete="new-password"
            placeholder={`Al menos ${MIN_PASSWORD} caracteres`}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <label className="row" style={{ gap: 6, fontSize: 14 }}>
          <input type="checkbox" checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} />
          Administrador
        </label>
        <button type="submit" className="btn" disabled={busy || !ready}>
          {busy ? 'Creando…' : 'Crear'}
        </button>
      </div>
    </form>
  );
}
