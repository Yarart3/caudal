import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from './auth/AuthContext';
import { Logo } from './Logo';

type Section = { name: string; path: string | null };

// Las pestañas completas llegan en la Fase 1c. De momento: Patrimonio (panel vacío) y
// Movimientos (que en la 1b solo tiene la pantalla de importar).
const SECTIONS: Section[] = [
  { name: 'Patrimonio', path: '/panel' },
  { name: 'Movimientos', path: '/importar' },
  { name: 'Inversiones', path: null },
  { name: 'Ajustes', path: null },
];

/** Marco de las pantallas con sesión: barra lateral, título y usuario (como en la maqueta). */
export function AppShell({
  title,
  current,
  children,
}: {
  title: string;
  current: string;
  children: ReactNode;
}) {
  const { user, logout, checkSession } = useAuth();
  const navigate = useNavigate();
  const [leaving, setLeaving] = useState(false);

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
            return (
              <button
                key={name}
                type="button"
                className={on ? 'on' : undefined}
                aria-current={on ? 'page' : undefined}
                disabled={path === null}
                title={path === null ? 'Disponible en próximas fases' : undefined}
                onClick={() => path && !on && navigate(path)}
              >
                {name}
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
          <h1 style={{ fontSize: 30 }}>{title}</h1>
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
        </header>
        {children}
      </main>
    </div>
  );
}
