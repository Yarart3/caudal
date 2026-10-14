import { useEffect, useState } from 'react';
import { Logo } from './Logo';

type Health = 'checking' | 'ok' | 'error';

// Pantalla provisional (parte 1.6): comprueba que la API y la BD responden.
// En el paso 3 se sustituye por el asistente, "¿Quién entra?" y el panel.
export default function App() {
  const [health, setHealth] = useState<Health>('checking');

  useEffect(() => {
    fetch('/api/health')
      .then((res) => setHealth(res.ok ? 'ok' : 'error'))
      .catch(() => setHealth('error'));
  }, []);

  const message = {
    checking: 'Comprobando la conexión…',
    ok: 'La app y la base de datos funcionan.',
    error: 'No se puede conectar con la API.',
  }[health];

  return (
    <main style={{ display: 'grid', placeItems: 'center', minHeight: '100vh', padding: 16 }}>
      <div className="card" style={{ padding: 28, width: 'min(420px, 100%)' }}>
        <div className="row">
          <Logo />
          <span className="num" style={{ fontWeight: 700, fontSize: 20 }}>
            Caudal
          </span>
        </div>
        <p className="muted">Fase 1a · parte 1.6</p>
        <p style={{ color: health === 'error' ? 'var(--bad)' : 'var(--ink)', fontWeight: 600 }}>
          {message}
        </p>
      </div>
    </main>
  );
}
