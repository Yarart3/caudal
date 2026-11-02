import { useState } from 'react';
import { api, errorMessage, type Goal } from '../api';
import { notifyDataChanged } from '../events';
import { formatEurRounded, parseEsAmount, toEsAmount } from '../format';
import { useDashboard } from '../hooks/useDashboard';
import { Modal } from './Modal';

const loadGoal = (month?: string) => api.goal(month);
const DEFAULT_NAME = 'Objetivo de patrimonio';

/** Objetivo de patrimonio (DISENO 8.4): meta, progreso e hitos. Uno por usuario. */
export function GoalCard({ month }: { month?: string }) {
  const { data, error } = useDashboard(loadGoal, month);
  const [editing, setEditing] = useState(false);

  return (
    <div className="card panel">
      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      {!data && !error && (
        <>
          <h2>Objetivo de patrimonio</h2>
          <p className="muted">Cargando…</p>
        </>
      )}
      {data && data.target_amount === null && (
        <>
          <h2>Objetivo de patrimonio</h2>
          <p className="muted">
            Fíjate una meta (por ejemplo, 50.000 €) y Caudal te enseñará cuánto llevas y cuáles son
            los siguientes hitos.
          </p>
          <div>
            <button type="button" className="btn btn-primary" onClick={() => setEditing(true)}>
              Poner objetivo
            </button>
          </div>
        </>
      )}
      {data && data.target_amount !== null && (
        <>
          <div className="between">
            <h2>{data.name}</h2>
            <span className="muted" style={{ fontSize: 13 }}>
              Meta:{' '}
              <strong style={{ color: 'var(--ink)' }}>
                {formatEurRounded(data.target_amount)}
              </strong>
            </span>
          </div>
          <div
            className="track"
            style={{ height: 14 }}
            role="progressbar"
            aria-label="Progreso del objetivo"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.min(data.percent ?? 0, 100)}
          >
            <div
              style={{
                width: `${Math.min(data.percent ?? 0, 100)}%`,
                background: 'var(--accent)',
                borderRadius: 99,
              }}
            />
          </div>
          <span style={{ fontSize: 14 }}>
            {data.percent} % conseguido
            {data.remaining !== null && Number(data.remaining) > 0
              ? ` · faltan ${formatEurRounded(data.remaining)}`
              : ' · ¡objetivo alcanzado!'}
          </span>
          {data.next_milestones.length > 0 && (
            <span className="muted" style={{ fontSize: 13 }}>
              Siguientes hitos: {data.next_milestones.map(formatEurRounded).join(' · ')}
            </span>
          )}
          <div>
            <button type="button" className="btn btn-sm" onClick={() => setEditing(true)}>
              Editar objetivo
            </button>
          </div>
        </>
      )}
      {editing && data && (
        <GoalDialog
          goal={data}
          month={month}
          onClose={() => setEditing(false)}
          onDone={() => {
            setEditing(false);
            notifyDataChanged();
          }}
        />
      )}
    </div>
  );
}

function GoalDialog({
  goal,
  month,
  onClose,
  onDone,
}: {
  goal: Goal;
  month?: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const exists = goal.target_amount !== null;
  const [name, setName] = useState(goal.name ?? DEFAULT_NAME);
  const [target, setTarget] = useState(exists ? toEsAmount(goal.target_amount ?? '') : '');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.SyntheticEvent) {
    event.preventDefault();
    const amount = parseEsAmount(target);
    if (amount === null) {
      setError('La meta tiene que ser un importe mayor que 0, como 50000 o 50.000,50.');
      return;
    }
    if (name.trim() === '') {
      setError('Ponle un nombre al objetivo.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.saveGoal(name.trim(), amount, month);
      onDone();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  async function handleDelete() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteGoal();
      onDone();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  if (confirmDelete) {
    return (
      <Modal title="¿Quitar el objetivo?" onClose={onClose}>
        <p className="note">
          Se borra la meta «{goal.name}». Tu patrimonio y tus movimientos no cambian; puedes poner
          otro objetivo cuando quieras.
        </p>
        {error && (
          <span className="err" role="alert">
            {error}
          </span>
        )}
        <div className="row" style={{ flexWrap: 'wrap' }}>
          <button type="button" className="btn btn-danger" onClick={handleDelete} disabled={busy}>
            {busy ? 'Quitando…' : 'Sí, quitar'}
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => setConfirmDelete(false)}
            disabled={busy}
          >
            Cancelar
          </button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title={exists ? 'Editar objetivo' : 'Poner objetivo'} onClose={onClose}>
      <form className="panel-form" onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="goal-name">Nombre</label>
          <input
            id="goal-name"
            type="text"
            maxLength={60}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="goal-target">Meta (€)</label>
          <input
            id="goal-target"
            type="text"
            inputMode="decimal"
            placeholder="Ej. 50000"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
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
          {exists && (
            <button
              type="button"
              className="link-btn danger"
              onClick={() => setConfirmDelete(true)}
              disabled={busy}
            >
              Quitar objetivo
            </button>
          )}
        </div>
      </form>
    </Modal>
  );
}
