import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { api } from './api';
import { useAuth } from './auth/AuthContext';
import { BackupIndicator } from './components/BackupIndicator';
import { onDataChanged } from './events';
import { Logo } from './Logo';

export type Section = 'Patrimonio' | 'Movimientos' | 'Inversiones' | 'Ajustes';

const SECTIONS: { name: Section; path: string }[] = [
  { name: 'Patrimonio', path: '/patrimonio' },
  { name: 'Movimientos', path: '/movimientos' },
  { name: 'Inversiones', path: '/inversiones' },
  { name: 'Ajustes', path: '/ajustes' },
];
// Las tres pestañas de la maqueta (Ajustes solo está en la barra lateral)
const TABS = SECTIONS.slice(0, 3);

/** Cuántos movimientos quedan por revisar. Se actualiza cuando cambian los datos. */
function useReviewCount(): number | null {
  const [count, setCount] = useState<number | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () => {
      api
        .transactions({ status: 'review', limit: 0 })
        .then((page) => alive && setCount(page.total))
        .catch(() => undefined); // el contador no es imprescindible
    };
    load();
    const off = onDataChanged(load);
    return () => {
      alive = false;
      off();
    };
  }, []);
  return count;
}

/** Marco de las pantallas con sesión: barra lateral, cabecera, pestañas y usuario (maqueta). */
export function AppShell({
  title,
  current,
  tabs = false,
  children,
}: {
  title: string;
  current: Section;
  /** Muestra las pestañas Patrimonio · Movimientos · Inversiones debajo del título */
  tabs?: boolean;
  children: ReactNode;
}) {
  const { user, logout, checkSession } = useAuth();
  const navigate = useNavigate();
  const [leaving, setLeaving] = useState(false);
  const reviewCount = useReviewCount();

  // Al volver a la pestaña, comprueba si la sesión ha caducado mientras tanto
  useEffect(() => {
    function onVisible() {
      if (document.visibilityState === 'visible') checkSession();
    }
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [checkSession]);

  if (!user) return null; // RequireAuth ya se encarga de mandar a "¿Quién entra?"

  async function handleLogout() {
    setLeaving(true);
    await logout();
    navigate('/entrar', { replace: true });
  }

  return (
    <div className="shell">
      <aside className="side">
        <div className="row" style={{ padding: '0 8px' }}>
          <Logo />
          <span className="num" style={{ fontWeight: 700, fontSize: 18 }}>
            Caudal
          </span>
        </div>
        <nav className="sidenav" aria-label="Secciones">
          {SECTIONS.map(({ name, path }) => {
            const on = name === current;
            const pending = name === 'Movimientos' && reviewCount ? reviewCount : 0;
            return (
              <button
                key={name}
                type="button"
                className={on ? 'on' : undefined}
                aria-current={on ? 'page' : undefined}
                onClick={() => navigate(path)}
              >
                {name}
                {pending > 0 && (
                  <span className="count" title={`${pending} por revisar`}>
                    {pending}
                    <span className="sr-only"> por revisar</span>
                  </span>
                )}
              </button>
            );
          })}
        </nav>
        <div className="sidefoot">
          <strong style={{ color: '#fff' }}>Solo en este ordenador</strong>
          <span>Tus datos no salen de casa.</span>
        </div>
      </aside>

      <main className="content">
        <header className="between">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <h1 style={{ fontSize: 30 }}>{title}</h1>
            <BackupIndicator />
          </div>
          <div className="row" style={{ flexWrap: 'wrap', gap: 12 }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => navigate('/movimientos/importar')}
            >
              Importar extracto
            </button>
            <div className="user-pill">
              <span
                className="avatar"
                style={{ width: 36, height: 36, fontSize: 15, background: user.color }}
                aria-hidden="true"
              >
                {user.initial}
              </span>
              <strong style={{ fontSize: 14 }}>{user.display_name}</strong>
              <button type="button" onClick={handleLogout} disabled={leaving}>
                {leaving ? 'Saliendo…' : 'Cerrar sesión'}
              </button>
            </div>
          </div>
        </header>
        {tabs && (
          <div className="tabs" role="group" aria-label="Pestañas">
            {TABS.map(({ name, path }) => (
              <button
                key={name}
                type="button"
                className={name === current ? 'on' : undefined}
                aria-pressed={name === current}
                onClick={() => name !== current && navigate(path)}
              >
                {name}
              </button>
            ))}
          </div>
        )}
        {children}
      </main>
    </div>
  );
}
