import { useNavigate } from 'react-router';
import { AppShell } from '../AppShell';
import { useAuth } from '../auth/AuthContext';

/** Pestaña Patrimonio. Los indicadores y gráficos llegan en la parte 1.5 de la Fase 1c. */
export function PanelPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <AppShell title="Patrimonio" current="Patrimonio" tabs>
      <section className="card empty">
        <h2>Tu patrimonio</h2>
        <p className="muted">
          Hola, {user?.display_name}. Aquí verás cuánto tienes y cómo evoluciona. Solo tú puedes ver
          lo que hay en tu panel.
        </p>
        <p className="muted">
          Mientras tanto, puedes importar extractos y revisar tus movimientos.
        </p>
        <div className="row" style={{ flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate('/movimientos/importar')}
          >
            Importar extracto
          </button>
          <button type="button" className="btn" onClick={() => navigate('/movimientos')}>
            Ver movimientos
          </button>
        </div>
      </section>
    </AppShell>
  );
}
