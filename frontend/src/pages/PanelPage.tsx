import { useNavigate } from 'react-router';
import { AppShell } from '../AppShell';
import { useAuth } from '../auth/AuthContext';

/** Panel vacío (Fase 1a). Las pestañas y su contenido llegan en la Fase 1c. */
export function PanelPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <AppShell title="Patrimonio" current="Patrimonio">
      <section className="card empty">
        <h2>Todavía no hay datos</h2>
        <p className="muted">
          Hola, {user?.display_name}. Aquí verás tu patrimonio, tus movimientos y tus inversiones.
          Solo tú puedes ver lo que hay en tu panel.
        </p>
        <p className="muted">Empieza importando el extracto de tu banco.</p>
        <div>
          <button type="button" className="btn btn-primary" onClick={() => navigate('/importar')}>
            Importar extracto
          </button>
        </div>
      </section>
    </AppShell>
  );
}
