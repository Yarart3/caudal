import { useNavigate } from 'react-router';
import { useAuth } from '../auth/AuthContext';
import { Screen } from './Screen';

// Provisional (parte 3.1). El panel con la barra lateral llega en la parte 3.4.
export function PanelPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate('/entrar', { replace: true });
  }

  return (
    <Screen>
      <h1>Hola, {user?.display_name}</h1>
      <p className="muted">Aquí irá el panel con la barra lateral (parte 3.4).</p>
      <button type="button" className="btn" onClick={handleLogout}>
        Cerrar sesión
      </button>
    </Screen>
  );
}
