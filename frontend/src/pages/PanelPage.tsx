import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '../auth/AuthContext';
import { Logo } from '../Logo';

const SECTIONS = ['Patrimonio', 'Movimientos', 'Inversiones', 'Ajustes'] as const;

/**
 * Panel vacío (Fase 1a): la estructura de la maqueta con la barra lateral, el usuario y
 * "Cerrar sesión". Las pestañas y su contenido llegan en la Fase 1c.
 */
export function PanelPage() {
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
          {SECTIONS.map((name, i) => (
            <button
              key={name}
              type="button"
              className={i === 0 ? 'on' : undefined}
              aria-current={i === 0 ? 'page' : undefined}
              disabled={i !== 0}
              title={i === 0 ? undefined : 'Disponible en próximas fases'}
            >
              {name}
            </button>
          ))}
        </nav>
        <div className="sidefoot">
          <strong style={{ color: '#fff' }}>Solo en este ordenador</strong>
          <span>Tus datos no salen de casa.</span>
        </div>
      </aside>

      <main className="content">
        <header className="between">
          <h1 style={{ fontSize: 30 }}>Patrimonio</h1>
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

        <section className="card empty">
          <h2>Todavía no hay datos</h2>
          <p className="muted">
            Hola, {user.display_name}. Aquí verás tu patrimonio, tus movimientos y tus inversiones.
            Solo tú puedes ver lo que hay en tu panel.
          </p>
          <p className="muted">El siguiente paso es importar los extractos del banco (Fase 1b).</p>
        </section>
      </main>
    </div>
  );
}
