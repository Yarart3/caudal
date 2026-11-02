import { useState } from 'react';
import { api, errorMessage, type BudgetLine, type BudgetStatus } from '../api';
import { notifyDataChanged } from '../events';
import { formatEur, parseEsAmount, toEsAmount } from '../format';
import { useDashboard } from '../hooks/useDashboard';
import { Modal } from './Modal';

const loadBudgets = (month?: string) => api.budgets(month);

const STATUS: Record<BudgetStatus, { label: string; text: string; bar: string }> = {
  ok: { label: 'OK', text: '#0B5747', bar: 'var(--accent)' },
  near: { label: 'Al límite', text: '#8A3A0C', bar: '#C98A1B' },
  over: { label: 'Superado', text: 'var(--bad)', bar: 'var(--bad)' },
};

/** Presupuestos del mes (DISENO 8.4): lo gastado frente a lo previsto en cada categoría. */
export function BudgetsCard({ month }: { month?: string }) {
  const { data, error } = useDashboard(loadBudgets, month);
  const [editing, setEditing] = useState(false);

  const withBudget = data?.lines.filter((line) => line.budget !== null) ?? [];

  return (
    <div className="card panel">
      <div className="between">
        <h2>Presupuestos del mes</h2>
        {data && data.lines.length > 0 && (
          <button type="button" className="btn btn-sm" onClick={() => setEditing(true)}>
            {withBudget.length > 0 ? 'Editar' : 'Poner presupuestos'}
          </button>
        )}
      </div>
      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      {!data && !error && <p className="muted">Cargando…</p>}
      {data && data.lines.length === 0 && (
        <p className="muted">
          Crea categorías de gasto en Ajustes para poder ponerles presupuesto.
        </p>
      )}
      {data && data.lines.length > 0 && withBudget.length === 0 && (
        <p className="muted">
          Aún no has puesto ningún presupuesto. Fija cuánto quieres gastar al mes en cada categoría
          y Caudal te dirá cómo vas.
        </p>
      )}
      {withBudget.map((line) => (
        <BudgetRow key={line.category_id} line={line} />
      ))}
      {data && withBudget.length > 0 && (
        <p className="muted" style={{ fontSize: 13 }}>
          Total: {formatEur(data.total_spent)} de {formatEur(data.total_budget)} presupuestados
        </p>
      )}
      {editing && data && (
        <BudgetsDialog
          lines={data.lines}
          month={month}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            notifyDataChanged();
          }}
        />
      )}
    </div>
  );
}

function BudgetRow({ line }: { line: BudgetLine }) {
  const status = STATUS[line.status ?? 'ok'];
  const width = Math.min(line.percent ?? 0, 100);
  return (
    <div className="budget-row">
      <div className="between" style={{ fontSize: 14, gap: 8 }}>
        <span style={{ fontWeight: 600 }}>{line.name}</span>
        <span className="muted">
          {formatEur(line.spent)} / {formatEur(line.budget ?? '0')} ·{' '}
          <strong style={{ color: status.text }}>{status.label}</strong>
        </span>
      </div>
      <div
        className="track"
        role="progressbar"
        aria-label={`Presupuesto de ${line.name}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.min(line.percent ?? 0, 100)}
      >
        <div style={{ width: `${width}%`, background: status.bar, borderRadius: 99 }} />
      </div>
    </div>
  );
}

/** Un campo por categoría de gasto; vacío = sin presupuesto. Solo se envía lo que ha cambiado. */
function BudgetsDialog({
  lines,
  month,
  onClose,
  onSaved,
}: {
  lines: BudgetLine[];
  month?: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const initial = Object.fromEntries(
    lines.map((l) => [l.category_id, l.budget === null ? '' : toEsAmount(l.budget)]),
  );
  const [values, setValues] = useState<Record<number, string>>(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.SyntheticEvent) {
    event.preventDefault();
    const changes: { category_id: number; amount: string | null }[] = [];
    for (const line of lines) {
      const text = values[line.category_id].trim();
      if (text === initial[line.category_id]) continue;
      if (text === '') {
        changes.push({ category_id: line.category_id, amount: null });
        continue;
      }
      const amount = parseEsAmount(text);
      if (amount === null) {
        setError(`El presupuesto de «${line.name}» no es válido. Usa un importe como 120 o 85,50.`);
        return;
      }
      changes.push({ category_id: line.category_id, amount });
    }
    if (changes.length === 0) {
      onClose();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.saveBudgets(changes, month);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Modal title="Presupuestos mensuales" onClose={onClose}>
      <form className="panel-form" onSubmit={handleSubmit} noValidate>
        <p className="note">
          Cuánto quieres gastar al mes en cada categoría. Déjalo vacío si no quieres presupuesto.
        </p>
        <div className="budget-fields">
          {lines.map((line) => (
            <div className="field budget-field" key={line.category_id}>
              <label htmlFor={`budget-${line.category_id}`}>
                <span className="dot" style={{ background: line.color }} /> {line.name}
              </label>
              <input
                id={`budget-${line.category_id}`}
                type="text"
                inputMode="decimal"
                placeholder="Sin presupuesto"
                value={values[line.category_id]}
                onChange={(e) => setValues({ ...values, [line.category_id]: e.target.value })}
              />
            </div>
          ))}
        </div>
        {error && (
          <span className="err" role="alert">
            {error}
          </span>
        )}
        <div className="row" style={{ flexWrap: 'wrap' }}>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? 'Guardando…' : 'Guardar'}
          </button>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            Cancelar
          </button>
        </div>
      </form>
    </Modal>
  );
}
