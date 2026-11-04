import { useState, type FormEvent } from 'react';
import { api, errorMessage, type Account } from '../api';
import { notifyDataChanged } from '../events';
import { Modal } from './Modal';

type Kind = 'mixed' | 'investment';

const PRESETS: { name: string; kind: Kind }[] = [
  { name: 'Trade Republic', kind: 'mixed' },
  { name: 'Scalable', kind: 'investment' },
];

/** Alta de una cuenta de broker (sin importador: las operaciones se apuntan a mano). */
export function InvestmentAccountDialog({
  existing,
  onClose,
  onCreated,
}: {
  existing: Account[];
  onClose: () => void;
  onCreated: (account: Account) => void;
}) {
  const taken = new Set(existing.map((a) => a.name.toLowerCase()));
  const first = PRESETS.find((p) => !taken.has(p.name.toLowerCase()));
  const [name, setName] = useState(first?.name ?? '');
  const [kind, setKind] = useState<Kind>(first?.kind ?? 'investment');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (name.trim() === '') return setError('Escribe el nombre del broker');
    setBusy(true);
    setError(null);
    try {
      const account = await api.createAccount({
        name: name.trim(),
        kind,
        import_format: null,
        liquidity_type: 'cash',
      });
      notifyDataChanged();
      onCreated(account);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Modal title="Añadir cuenta de inversión" onClose={onClose}>
      <form className="panel-form" onSubmit={handleSubmit} noValidate>
        <div className="row" role="group" aria-label="Brokers habituales" style={{ gap: 8 }}>
          {PRESETS.filter((p) => !taken.has(p.name.toLowerCase())).map((p) => (
            <button
              key={p.name}
              type="button"
              className={`toggle${name === p.name ? ' on-i' : ''}`}
              aria-pressed={name === p.name}
              onClick={() => {
                setName(p.name);
                setKind(p.kind);
              }}
            >
              {p.name}
            </button>
          ))}
        </div>
        <div className="field">
          <label htmlFor="acc-name">Nombre</label>
          <input
            id="acc-name"
            type="text"
            maxLength={60}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="acc-kind">Qué tienes ahí</label>
          <select id="acc-kind" value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
            <option value="mixed">Inversiones y efectivo (como Trade Republic)</option>
            <option value="investment">Solo inversiones (como Scalable)</option>
          </select>
        </div>
        <p className="muted" style={{ fontSize: 13 }}>
          Caudal no importa extractos de brokers: las compras y ventas se apuntan a mano o con la
          plantilla.
        </p>
        {error && (
          <span className="err" role="alert">
            {error}
          </span>
        )}
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Guardando…' : 'Añadir cuenta'}
        </button>
      </form>
    </Modal>
  );
}
