import '@fontsource-variable/manrope';
import '@fontsource-variable/space-grotesk';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';
import { initTheme } from './theme';

initTheme(); // antes de pintar, para que no parpadee el tema claro

const root = document.getElementById('root');
if (!root) throw new Error('No se encuentra el elemento #root');

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
