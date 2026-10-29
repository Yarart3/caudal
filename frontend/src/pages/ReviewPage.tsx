import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { api, errorMessage, type Transaction } from '../api';
import { AppShell } from '../AppShell';
import { ApplyAlways } from '../components/ApplyAlways';
import { appliedMessage } from '../components/applyAlwaysResult';
import { CategorySelect } from '../components/CategorySelect';
import { notifyDataChanged, onDataChanged } from '../events';
import { formatDate, formatSigned } from '../format';
import { useLookups } from '../hooks/useLookups';

const LIMIT = 200;

/** Movimiento al que se le acaba de poner categoría: falta contestar «¿Aplicar siempre?» */
type Asking = { tx: Transaction; categoryId: number };

/**
 * Revisar (DISENO 9.4): los movimientos sin categoría, uno a uno. Al elegir la categoría se
 * guarda como puesta a mano y se ofrece crear la regla para los siguientes.
 */
export function ReviewPage() {
  const navigate = useNavigate();
  const { lookups, error: lookupError } = useLookups();
  const [items, setItems] = useState<Transaction[] | null>(null);
  const [total, setTotal] = useState(0);
  const [reload, setReload] = useState(0);
  const [asking, setAsking] = useState<Asking | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .transactions({ status: 'review', limit: LIMIT })
      .then((page) => {
        if (!alive) return;
        setItems(page.items);
        setTotal(page.total);
      })
      .catch((err: unknown) => alive && setError(errorMessage(err)));
    return () => {
      alive = false;
    };
  }, [reload]);

  useEffect(() => onDataChanged(() => setReload((n) => n + 1)), []);

  const accountName = (id: number) => lookups?.accounts.find((a) => a.id === id)?.name ?? '';
  const categoryName = (id: number) => lookups?.categories.find((c) => c.id === id)?.name ?? '';

  async function setCategory(tx: Transaction, categoryId: number | null) {
    if (categoryId === null) return;
    setBusyId(tx.id);
    setError(null);
    setMessage(null);
    try {
      const saved = await api.updateTransaction(tx.id, { category_id: categoryId });
      setAsking({ tx: saved, categoryId });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  async function markInternal(tx: Transaction) {
    setBusyId(tx.id);
    setError(null);
    try {
      await api.updateTransaction(tx.id, { is_internal_transfer: true });
      setMessage(`«${tx.description}» marcado como transferencia entre tus cuentas`);
      notifyDataChanged(); // recarga la lista y el contador
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <AppShell title="Revisar" current="Movimientos">
      <div className="row">
        <button type="button" className="link-btn" onClick={() => navigate('/movimientos')}>
          ← Volver a Movimientos
        </button>
      </div>
      {(error || lookupError) && (
        <p className="err" role="alert">
          {error ?? lookupError}
        </p>
      )}
      {message && (
        <p className="ok" role="status">
          {message}
        </p>
      )}

      <section className="card panel">
        <div className="between">
          <h2>Por revisar</h2>
          <span className="muted" style={{ fontSize: 13 }}>
            {items === null
              ? 'Cargando…'
              : `${total} ${total === 1 ? 'movimiento' : 'movimientos'}`}
          </span>
        </div>
        <p className="muted" style={{ fontSize: 14 }}>
          Ninguna regla sabe a qué categoría van. Elige una: si creas la regla, los siguientes con
          el mismo concepto se categorizarán solos.
        </p>

        {items !== null && items.length === 0 && !asking && (
          <div className="result">
            <strong>Todo está categorizado.</strong>
            <span>
              Cuando importes otro extracto, lo que no encaje con tus reglas aparecerá aquí.
            </span>
          </div>
        )}

        {items !== null && items.length > 0 && (
          <ul className="review-list">
            {items.map((tx) => {
              const isAsking = asking?.tx.id === tx.id;
              return (
                <li key={tx.id} className="review-item">
                  <div className="between" style={{ alignItems: 'flex-start' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                      <strong style={{ overflowWrap: 'anywhere' }}>{tx.description}</strong>
                      <span className="muted" style={{ fontSize: 13 }}>
                        {formatDate(tx.date)} · {accountName(tx.account_id)}
                      </span>
                    </div>
                    <strong
                      className="tnum"
                      style={{
                        whiteSpace: 'nowrap',
                        color: Number(tx.amount) > 0 ? '#0B5747' : 'var(--ink)',
                      }}
                    >
                      {formatSigned(tx.amount)}
                    </strong>
                  </div>

                  {isAsking && asking ? (
                    <ApplyAlways
                      description={tx.description}
                      categoryId={asking.categoryId}
                      categoryName={categoryName(asking.categoryId)}
                      onDone={(result) => {
                        setAsking(null);
                        setMessage(
                          appliedMessage(result) ??
                            `«${tx.description}» → ${categoryName(asking.categoryId)}`,
                        );
                        notifyDataChanged(); // recarga la lista y el contador
                      }}
                    />
                  ) : (
                    <div className="row" style={{ flexWrap: 'wrap' }}>
                      <div className="field" style={{ flex: '1 1 220px' }}>
                        <CategorySelect
                          ariaLabel={`Categoría de ${tx.description}`}
                          categories={lookups?.categories ?? []}
                          value={null}
                          onChange={(categoryId) => void setCategory(tx, categoryId)}
                          emptyLabel="Elige la categoría…"
                          disabled={busyId !== null || asking !== null || !lookups}
                        />
                      </div>
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => void markInternal(tx)}
                        disabled={busyId !== null || asking !== null}
                      >
                        Es un traspaso entre mis cuentas
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        {total > LIMIT && (
          <p className="muted" style={{ fontSize: 13 }}>
            Se ven los {LIMIT} más recientes. Al ir revisándolos aparecerán los siguientes.
          </p>
        )}
      </section>
    </AppShell>
  );
}
