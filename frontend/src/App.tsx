import type { ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import { AuthProvider } from './auth/AuthProvider';
import { RequireAuth } from './auth/RequireAuth';
import { ImportPage } from './pages/ImportPage';
import { InvestmentsPage } from './pages/InvestmentsPage';
import { LoginPage } from './pages/LoginPage';
import { MovementsPage } from './pages/MovementsPage';
import { PanelPage } from './pages/PanelPage';
import { ReviewPage } from './pages/ReviewPage';
import { SettingsPage } from './pages/SettingsPage';
import { SetupPage } from './pages/SetupPage';
import { StartPage } from './pages/StartPage';

/** Pantallas que necesitan sesión */
const PRIVATE: { path: string; element: ReactNode }[] = [
  { path: '/patrimonio', element: <PanelPage /> },
  { path: '/movimientos', element: <MovementsPage /> },
  { path: '/movimientos/importar', element: <ImportPage /> },
  { path: '/movimientos/revisar', element: <ReviewPage /> },
  { path: '/inversiones', element: <InvestmentsPage /> },
  { path: '/ajustes', element: <SettingsPage /> },
];

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<StartPage />} />
          <Route path="/bienvenida" element={<SetupPage />} />
          <Route path="/entrar" element={<LoginPage />} />
          {PRIVATE.map(({ path, element }) => (
            <Route key={path} path={path} element={<RequireAuth>{element}</RequireAuth>} />
          ))}
          {/* Direcciones de las fases 1a y 1b, por si quedaron en el historial del navegador */}
          <Route path="/panel" element={<Navigate to="/patrimonio" replace />} />
          <Route path="/importar" element={<Navigate to="/movimientos/importar" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
