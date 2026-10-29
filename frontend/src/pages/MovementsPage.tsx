import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import {
  api,
  errorMessage,
  type StatusFilter,
  type Transaction,
  type TransactionFilters,
} from '../api';
import { AppShell } from '../AppShell';
import { CategorySelect } from '../components/CategorySelect';
import { StatusBadge } from '../components/StatusBadge';
import { TransactionDialog } from '../components/TransactionDialog';
import { onDataChanged } from '../events';
import { formatDate, formatMonth, formatSigned, recentMonths } from '../format';
import { useDebounced } from '../hooks/useDebounced';
import { useLookups } from '../hooks/useLookups';

const PAGE_SIZE = 100;
const MONTHS = recentMonths(24);
const STATUSES: { value: StatusFilter; label: string }[] = [
  { value: 'review', label: 'Por revisar' },
  { value: 'auto', label: 'Automática' },
  { value: 'manual', label: 'Puesta a mano' },
  { value: 'internal', label: 'Transferencias internas' },
];

type Filters = {
  q: string;
  month: string;
  category: number | null;
  status: StatusFilter | '';
  account: number | null;
};
const NO_FILTERS: Filters = { q: '', month: '', category: null, status: '', account: null };

type Loaded = { key: string; items: Transaction[]; total: number };
/** null = cerrado · 'new' = alta · Transaction = edición */
type Editing = null | 'new' | Transaction;

/**
 * Pestaña Movimientos (Fase 1c, parte 1.4): tabla con buscador y filtros, alta, edición y
 * borrado. Los indicadores y gráficos de arriba llegan en la parte 1.5.
 */
export function MovementsPage() {
  const navigate = useNavigate();
  const { lookups, error: lookupError } = useLookups();
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const q = useDebounced(filters.q.trim(), 300);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [moreBusy, setMoreBusy] = useState(false);
  const [editing, setEditing] = useState<Editing>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [reviewCount, setReviewCount] = useState(0);

  const query: TransactionFilters = useMemo(
    () => ({
      q: q || undefined,
      month: filters.month || undefined,
      category: filters.category ?? undefined,
      status: filters.status || undefined,
      account: filters.account ?? undefined,
    }),
    [q, filters.month, filters.category, filters.status, filters.account],
  );
  const key = JSON.stringify(query);

  // Primera página con los filtros actuales. Se vuelve a pedir si cambian los datos.
  useEffect(() => {
    let alive = true;
    api
      .transactions({ ...query, limit: PAGE_SIZE })
      .then((page) => {
        if (!alive) return;
        setLoaded({ key, ...page });
        setError(null);
      })
      .catch((err: unknown) => alive && setError(errorMessage(err)));
    api
      .transactions({ status: 'review', limit: 0 })
      .then((page) => alive && setReviewCount(page.total))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [query, key, reload]);

  useEffect(() => onDataChanged(() => setReload((n) => n + 1)), []);

  async function loadMore() {
    if (!loaded) return;
    setMoreBusy(true);
    try {
      const page = await api.transactions({
        ...query,
        limit: PAGE_SIZE,
        offset: loaded.items.length,
      });
      setLoaded({ key: loaded.key, items: [...loaded.items, ...page.items], total: page.total });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setMoreBusy(false);
    }
  }

  const accountName = (id: number) => lookups?.accounts.find((a) => a.id === id)?.name ?? '';
  const categoryName = (id: number | null) =>
    id === null ? null : (lookups?.categories.find((c) => c.id === id)?.name ?? null);
  const loading = loaded === null || loaded.key !== key;
  const hasFilters = JSON.stringify(filters) !== JSON.stringify(NO_FILTERS);
  const set = (changes: Partial<Filters>) => setFilters((f) => ({ ...f, ...changes }));

  return (
    <AppShell title="Movimientos" current="Movimientos" tabs>
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

      {reviewCount > 0 && (
        <div className="infobar">
          <span>
            <strong style={{ color: 'var(--ink)' }}>{reviewCount}</strong>{' '}
            {reviewCount === 1 ? 'movimiento por revisar' : 'movimientos por revisar'}: ponles
            categoría para que cuenten bien en los totales.
          </span>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => navigate('/movimientos/revisar')}
          >
            Revisar ahora
          </button>
        </div>
      )}

      <section className="card panel">
        <div className="between">
          <h2>Movimientos</h2>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setEditing('new')}
            disabled={!lookups || lookups.accounts.length === 0}
          >
            + Añadir movimiento
          </button>
        </div>

        <div className="filters">
          <div className="field grow">
            <label htmlFor="f-buscar">Buscar</label>
            <input
              id="f-buscar"
              type="search"
              placeholder="Concepto o categoría…"
              value={filters.q}
              onChange={(e) => set({ q: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="f-mes">Mes</label>
            <select
              id="f-mes"
              value={filters.month}
              onChange={(e) => set({ month: e.target.value })}
            >
              <option value="">Todos</option>
              {MONTHS.map((m) => (
                <option key={m} value={m}>
                  {formatMonth(m)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-categoria">Categoría</label>
            <CategorySelect
              id="f-categoria"
              categories={lookups?.categories ?? []}
              value={filters.category}
              onChange={(category) => set({ category })}
              emptyLabel="Todas"
            />
          </div>
          <div className="field">
            <label htmlFor="f-estado">Estado</label>
            <select
              id="f-estado"
              value={filters.status}
              onChange={(e) => set({ status: e.target.value as StatusFilter | '' })}
            >
              <option value="">Todos</option>
              {STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-cuenta">Cuenta</label>
            <select
              id="f-cuenta"
              value={filters.account ?? ''}
              onChange={(e) => set({ account: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">Todas</option>
              {lookups?.accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="between muted" style={{ fontSize: 13 }}>
          <span aria-live="polite">
            {loading
              ? 'Cargando…'
              : `${loaded.total} ${loaded.total === 1 ? 'movimiento' : 'movimientos'}`}
          </span>
          {hasFilters && (
            <button type="button" className="link-btn" onClick={() => setFilters(NO_FILTERS)}>
              Quitar filtros
            </button>
          )}
        </div>

        {!loading && loaded.items.length === 0 ? (
          <p className="muted">
            {hasFilters
              ? 'Ningún movimiento con estos filtros.'
              : 'Todavía no hay movimientos. Importa un extracto o añade uno a mano.'}
          </p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ minWidth: 680 }} aria-busy={loading}>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Cuenta</th>
                  <th>Concepto</th>
                  <th>Categoría</th>
                  <th className="r">Importe</th>
                  <th className="r">
                    <span className="sr-only">Acciones</span>
                  </th>
                </tr>
              </thead>
              <tbody style={{ opacity: loading ? 0.5 : 1 }}>
                {(loaded?.items ?? []).map((tx) => (
                  <tr key={tx.id}>
                    <td className="muted tnum" style={{ whiteSpace: 'nowrap' }}>
                      {formatDate(tx.date)}
                    </td>
                    <td className="muted">{accountName(tx.account_id)}</td>
                    <td style={{ fontWeight: 600 }}>{tx.description}</td>
                    <td>
                      <span className="row" style={{ gap: 6, display: 'inline-flex' }}>
                        {categoryName(tx.category_id) ??
                          (tx.is_internal_transfer ? '' : <span className="muted">—</span>)}
                        <StatusBadge tx={tx} />
                      </span>
                    </td>
                    <td
                      className="r tnum"
                      style={{
                        fontWeight: 700,
                        whiteSpace: 'nowrap',
                        color: tx.is_internal_transfer
                          ? 'var(--muted)'
                          : Number(tx.amount) > 0
                            ? '#0B5747'
                            : 'var(--ink)',
                      }}
                    >
                      {formatSigned(tx.amount)}
                    </td>
                    <td className="r">
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => setEditing(tx)}
                        disabled={!lookups}
                        aria-label={`Editar ${tx.description}`}
                      >
                        Editar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && loaded.items.length < loaded.total && (
          <button type="button" className="btn" onClick={loadMore} disabled={moreBusy}>
            {moreBusy ? 'Cargando…' : `Ver más (${loaded.total - loaded.items.length} más)`}
          </button>
        )}
      </section>

      {editing !== null && lookups && (
        <TransactionDialog
          tx={editing === 'new' ? null : editing}
          accounts={lookups.accounts}
          categories={lookups.categories}
          onClose={() => setEditing(null)}
          onFinished={(text) => {
            setEditing(null);
            setMessage(text);
          }}
        />
      )}
    </AppShell>
  );
}
