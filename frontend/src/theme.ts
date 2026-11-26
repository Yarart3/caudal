/**
 * Tema claro / oscuro (Fase 5).
 *
 * - «auto» (por defecto) sigue al sistema (prefers-color-scheme, en styles.css).
 * - «light» / «dark» lo fuerzan con el atributo data-theme de <html>.
 * La elección se guarda en el navegador (localStorage): es una preferencia de este equipo, no
 * un dato de la app, así que no va a la BD ni a los backups. Si el navegador no deja guardarla
 * (ventana privada), funciona igual en «auto».
 */
export type Theme = 'auto' | 'light' | 'dark';

const KEY = 'caudal-theme';

export function getTheme(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    return value === 'light' || value === 'dark' ? value : 'auto';
  } catch {
    return 'auto';
  }
}

function apply(theme: Theme): void {
  if (theme === 'auto') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}

export function setTheme(theme: Theme): void {
  try {
    if (theme === 'auto') localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, theme);
  } catch {
    // sin almacenamiento: se aplica solo mientras la página esté abierta
  }
  apply(theme);
}

/** Al arrancar (main.tsx): aplica el tema guardado y, al imprimir, siempre el claro. */
export function initTheme(): void {
  apply(getTheme());
  window.addEventListener('beforeprint', () => apply('light'));
  window.addEventListener('afterprint', () => apply(getTheme()));
}
