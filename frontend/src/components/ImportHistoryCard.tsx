import { useEffect, useState } from 'react';
import { api, errorMessage, type Account, type ImportRecord } from '../api';
import { notifyDataChanged, onDataChanged } from '../events';
import { formatDate, formatMoment } from '../format';
import { Modal } from './Modal';

function period(record: ImportRecord): string {
  if (!record.first_date || !record.last_date) return '';
  return record.first_date === record.last_date
    ? formatDate(record.first_date)
    : `del ${formatDate(record.first_date)} al ${formatDate(record.last_date)}`;
}

function movements(count: number): string {
  return `${count} ${count === 1 ? 'movimiento' : 'movimientos'}`;
}

/**
 * Últimas importaciones con «Deshacer» (Fase 5): borra los movimientos que entraron con esa
 * importación y deja la cuenta como estaba.
 */
export function ImportHistoryCard({ accounts }: { accounts: Account[] }) {
  const [records, setRecords] = useState<ImportRecord[] | null>(null);
  const [reload, setReload] = useState(0);
  const [confirming, setConfirming] = useState<ImportRecord | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .imports()
      .then((list) => alive && setRecords(list))
      .catch((err: unknown) => alive && setError(errorMessage(err)));
    return () => {
      alive = false;
    };
  }, [reload]);

  useEffect(() => onDataChanged(() => setReload((n) => n + 1)), []);

  const accountName = (id: number) => accounts.find((a) => a.id === id)?.name ?? 'Cuenta';

  async function undo(record: ImportRecord) {
    setBusy(true);
    setError(null);
    try {
      const result = await api.undoImport(record.id);
      const parts = [`Importación deshecha: ${movements(result.deleted)} borrados`];
      if (result.unpaired > 0) {
        parts.push(
          `${result.unpaired} ${
            result.unpaired === 1
              ? 'transferencia de otra cuenta vuelve'
              : 'transferencias de otras cuentas vuelven'
          } a contar como gasto o ingreso (revísalas)`,
        );
      }
      if (result.balance_restored) parts.push('el saldo de la cuenta vuelve al de antes');
      setMessage(parts.join(' · '));
      setConfirming(null);
      notifyDataChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (records === null && !error) return null;

  return (
    <section className="card panel">
      <h2>Últimas importaciones</h2>
      {message && (
        <p className="ok" role="status">
          {message}
        </p>
      )}
      {error && !confirming && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      {records !== null && records.length === 0 ? (
        <p className="muted">
          Aquí saldrán tus importaciones, por si alguna vez te equivocas de archivo o de cuenta y
          quieres deshacerla.
        </p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ minWidth: 520 }}>
            <thead>
              <tr>
                <th>Importado</th>
                <th>Cuenta</th>
                <th>Movimientos</th>
                <th className="r">
                  <span className="sr-only">Acción</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {(records ?? []).map((record) => (
                <tr key={record.id}>
                  <td className="muted tnum" style={{ whiteSpace: 'nowrap' }}>
                    {formatMoment(record.created_at)}
                  </td>
                  <td style={{ fontWeight: 600 }}>{accountName(record.account_id)}</td>
                  <td>
                    {movements(record.remaining)}{' '}
                    <span className="muted" style={{ fontSize: 13 }}>
                      {period(record)}
                    </span>
                  </td>
                  <td className="r">
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => {
                        setMessage(null);
                        setError(null);
                        setConfirming(record);
                      }}
                    >
                      Deshacer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {confirming && (
        <Modal title="¿Deshacer esta importación?" onClose={() => !busy && setConfirming(null)}>
          <p>
            Se borrarán los <strong>{movements(confirming.remaining)}</strong> que entraron en{' '}
            <strong>{accountName(confirming.account_id)}</strong> {period(confirming)}, también los
            que hayas editado o categorizado después.
          </p>
          <p className="note">
            Si vuelves a importar ese extracto, volverán a entrar. Lo que ya estaba antes de esta
            importación no se toca.
          </p>
          {error && (
            <span className="err" role="alert">
              {error}
            </span>
          )}
          <div className="row" style={{ flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => void undo(confirming)}
              disabled={busy}
            >
              {busy ? 'Deshaciendo…' : 'Sí, deshacer'}
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => setConfirming(null)}
              disabled={busy}
            >
              Cancelar
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}
