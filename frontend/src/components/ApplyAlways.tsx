import { useState, type FormEvent } from 'react';
import { api, errorMessage } from '../api';
import { notifyDataChanged } from '../events';
import { suggestPattern } from '../format';
import type { ApplyAlwaysResult } from './applyAlwaysResult';

/**
 * «¿Aplicar siempre a 'X'?» (DISENO 9.4): después de poner una categoría a mano, ofrece crear
 * la regla con el texto del concepto (editable) y la aplica a los que están por revisar.
 */
export function ApplyAlways({
  description,
  categoryId,
  categoryName,
  onDone,
}: {
  description: string;
  categoryId: number;
  categoryName: string;
  onDone: (result: ApplyAlwaysResult) => void;
}) {
  const [pattern, setPattern] = useState(() => suggestPattern(description));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Los Bizum pueden ser cualquier cosa: se revisan siempre uno a uno (DISENO 9.4)
  if (/^BIZUM\b/.test(suggestPattern(description))) {
    return (
      <div className="ask">
        <span>Los Bizum se revisan siempre uno a uno, así que no se crea ninguna regla.</span>
        <div className="row">
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => onDone({ created: false, categorized: 0, pattern: '' })}
          >
            Vale
          </button>
        </div>
      </div>
    );
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (pattern.trim() === '') return setError('Escribe el texto que tiene que contener');
    setBusy(true);
    setError(null);
    try {
      const saved = await api.saveRule({ pattern, category_id: categoryId, apply: true });
      notifyDataChanged();
      onDone({ created: true, categorized: saved.categorized, pattern: saved.rule.pattern });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <form className="ask" onSubmit={handleSubmit} noValidate>
      <label htmlFor={`pattern-${categoryId}`} style={{ fontWeight: 600 }}>
        ¿Aplicar siempre? Los conceptos que contengan…
      </label>
      <input
        id={`pattern-${categoryId}`}
        className="input"
        type="text"
        maxLength={120}
        value={pattern}
        onChange={(e) => setPattern(e.target.value)}
      />
      <span className="muted" style={{ fontSize: 13 }}>
        …irán a <strong style={{ color: 'var(--ink)' }}>{categoryName}</strong>, también los que ya
        están por revisar. Compara palabras enteras: puedes quitar las que sobren.
      </span>
      {error && (
        <span className="err" role="alert">
          {error}
        </span>
      )}
      <div className="row" style={{ flexWrap: 'wrap' }}>
        <button type="submit" className="btn btn-sm btn-accent" disabled={busy}>
          {busy ? 'Creando…' : 'Sí, crear la regla'}
        </button>
        <button
          type="button"
          className="btn btn-sm"
          disabled={busy}
          onClick={() => onDone({ created: false, categorized: 0, pattern: '' })}
        >
          No, solo este
        </button>
      </div>
    </form>
  );
}
