import { useState } from 'react';
import { getTheme, setTheme, type Theme } from '../theme';

const OPTIONS: { value: Theme; label: string }[] = [
  { value: 'auto', label: 'Automático' },
  { value: 'light', label: 'Claro' },
  { value: 'dark', label: 'Oscuro' },
];

/** Ajustes → Apariencia (Fase 5): tema claro, oscuro o el del sistema, en este navegador. */
export function AppearanceCard() {
  const [theme, setCurrent] = useState<Theme>(getTheme);

  function choose(value: Theme) {
    setTheme(value);
    setCurrent(value);
  }

  return (
    <section className="card panel">
      <h2>Apariencia</h2>
      <div className="row" role="group" aria-label="Tema" style={{ gap: 8, flexWrap: 'wrap' }}>
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            className={`toggle${theme === option.value ? ' on-i' : ''}`}
            aria-pressed={theme === option.value}
            onClick={() => choose(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
      <p className="muted" style={{ fontSize: 13, margin: 0 }}>
        «Automático» usa el modo claro u oscuro del sistema. Se guarda en este navegador: en el
        móvil o en el otro ordenador se elige aparte. Al imprimir, siempre sale en claro.
      </p>
    </section>
  );
}
