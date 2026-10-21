import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import { AuthProvider } from './auth/AuthProvider';
import { RequireAuth } from './auth/RequireAuth';
import { ImportPage } from './pages/ImportPage';
import { LoginPage } from './pages/LoginPage';
import { PanelPage } from './pages/PanelPage';
import { SetupPage } from './pages/SetupPage';
import { StartPage } from './pages/StartPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<StartPage />} />
          <Route path="/bienvenida" element={<SetupPage />} />
          <Route path="/entrar" element={<LoginPage />} />
          <Route
            path="/panel"
            element={
              <RequireAuth>
                <PanelPage />
              </RequireAuth>
            }
          />
          <Route
            path="/importar"
            element={
              <RequireAuth>
                <ImportPage />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
