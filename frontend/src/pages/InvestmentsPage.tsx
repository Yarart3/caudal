import { useCallback, useEffect, useState } from 'react';
import { AppShell } from '../AppShell';
import {
  api,
  errorMessage,
  type Account,
  type Benchmark,
  type InvestmentSummary,
  type Operation,
  type Positions,
  type PriceStatus,
  type Product,
} from '../api';
import { InvestmentAccountDialog } from '../components/InvestmentAccountDialog';
import { InvestmentImportCard } from '../components/InvestmentImportCard';
import { OperationDialog, type OperationMode } from '../components/OperationDialog';
import { PortfolioOverview } from '../components/PortfolioOverview';
import { ProductDialog } from '../components/ProductDialog';
import { notifyDataChanged, onDataChanged } from '../events';
import { formatDate, formatEur, formatMoment, formatPrice, formatShares } from '../format';
import { kindLabel, operationLabel } from '../investmentLabels';

type Data = {
  accounts: Account[];
  products: Product[];
  operations: Operation[];
  prices: PriceStatus;
  summary: InvestmentSummary;
  positions: Positions;
  benchmark: Benchmark;
};

type Dialog =
  | { kind: 'account' }
  | { kind: 'product'; product: Product | null }
  | { kind: 'operation'; mode: OperationMode };

const STALE_BADGE = { background: '#FBE6D4', color: '#8A3A0C' };

/**
 * Pestaña Inversiones (Fase 3). Arriba, la cartera como en la maqueta (parte 3.5): indicadores,
 * posiciones, aportaciones, comparativa, dividendos, rentabilidad por año y costes. Debajo, lo
 * de apuntar (partes 3.3d1 y 3.3d2): operaciones, productos, importar el historial y cuentas.
 */
export function InvestmentsPage() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(() => {
    Promise.all([
      api.accounts(),
      api.products(),
      api.operations(),
      api.priceStatus(),
      api.investmentSummary(),
      api.positions(),
      api.benchmark(),
    ])
      .then(([accounts, products, operations, prices, summary, positions, benchmark]) => {
        setData({
          accounts: accounts.filter((a) => a.kind === 'investment' || a.kind === 'mixed'),
          products,
          operations,
          prices,
          summary,
          positions,
          benchmark,
        });
        setError(null);
      })
      .catch((err: unknown) => setError(errorMessage(err)));
  }, []);

  useEffect(() => {
    load();
    return onDataChanged(load);
  }, [load]);

  async function refreshPrices(quiet = false) {
    setRefreshing(true);
    try {
      const result = await api.refreshPrices();
      const failed = result.status.products.filter((p) => p.stale).length;
      if (!quiet) {
        setMessage(
          failed === 0
            ? 'Precios actualizados'
            : `Precios actualizados, salvo ${failed} producto${failed === 1 ? '' : 's'}`,
        );
      }
      notifyDataChanged();
    } catch (err) {
      if (!quiet) setError(errorMessage(err));
    } finally {
      setRefreshing(false);
    }
  }

  function finish(text: string, refresh = false) {
    setDialog(null);
    setMessage(text);
    if (refresh) void refreshPrices(true); // histórico del producto nuevo, sin esperar
  }

  return (
    <AppShell title="Inversiones" current="Inversiones" tabs>
      {message && (
        <p className="ok" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      {data === null ? (
        !error && <p className="muted">Cargando…</p>
      ) : data.accounts.length === 0 ? (
        <section className="card empty" style={{ alignItems: 'center', textAlign: 'center' }}>
          <h2>Todavía no hay inversiones</h2>
          <p className="muted">
            Añade tu cuenta de broker (Trade Republic, Scalable…) para apuntar tus compras y ver
            aquí tu cartera.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setDialog({ kind: 'account' })}
          >
            Añadir cuenta de inversión
          </button>
        </section>
      ) : (
        <>
          <PricesBar data={data} refreshing={refreshing} onRefresh={() => void refreshPrices()} />
          {data.summary.has_investments && (
            <PortfolioOverview
              summary={data.summary}
              positions={data.positions}
              benchmark={data.benchmark}
              operations={data.operations}
              onAddOperation={() => setDialog({ kind: 'operation', mode: { kind: 'new' } })}
            />
          )}
          <OperationsCard data={data} onOpen={(mode) => setDialog({ kind: 'operation', mode })} />
          <ProductsCard
            data={data}
            onAdd={() => setDialog({ kind: 'product', product: null })}
            onEdit={(product) => setDialog({ kind: 'product', product })}
          />
          <InvestmentImportCard
            accounts={data.accounts}
            hasProducts={data.products.length > 0}
            onImported={(text) => finish(text, true)}
          />
          <AccountsCard data={data} onAdd={() => setDialog({ kind: 'account' })} />
        </>
      )}

      {dialog?.kind === 'account' && data && (
        <InvestmentAccountDialog
          existing={data.accounts}
          onClose={() => setDialog(null)}
          onCreated={(account) => finish(`Cuenta «${account.name}» añadida`)}
        />
      )}
      {dialog?.kind === 'product' && (
        <ProductDialog
          product={dialog.product}
          onClose={() => setDialog(null)}
          onFinished={(text) => finish(text, dialog.product === null)}
        />
      )}
      {dialog?.kind === 'operation' && data && (
        <OperationDialog
          mode={dialog.mode}
          accounts={data.accounts}
          products={data.products}
          onClose={() => setDialog(null)}
          onFinished={(text) => finish(text)}
        />
      )}
    </AppShell>
  );
}

function AccountsCard({ data, onAdd }: { data: Data; onAdd: () => void }) {
  return (
    <section className="card panel">
      <div className="between">
        <h2>Cuentas de inversión</h2>
        <button type="button" className="btn btn-sm" onClick={onAdd}>
          + Añadir cuenta
        </button>
      </div>
      <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
        {data.accounts.map((a) => (
          <span key={a.id} className="badge" style={{ background: 'var(--soft)', fontSize: 13 }}>
            {a.name} · {a.kind === 'mixed' ? 'inversiones y efectivo' : 'inversiones'}
          </span>
        ))}
      </div>
    </section>
  );
}

/** Barra de arriba: cuándo se actualizaron los precios y el botón para hacerlo ya. */
function PricesBar({
  data,
  refreshing,
  onRefresh,
}: {
  data: Data;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  if (!data.products.some((p) => p.price_source !== 'manual')) return null;
  return (
    <div className="infobar">
      <span>
        {data.prices.last_refresh ? (
          <>
            <strong style={{ color: 'var(--ink)' }}>
              Precios actualizados {formatMoment(data.prices.last_refresh)}
            </strong>{' '}
            · ETFs y acciones con ~15 min de retraso
          </>
        ) : (
          'Todavía no se han descargado precios'
        )}
      </span>
      <button type="button" className="btn btn-sm" onClick={onRefresh} disabled={refreshing}>
        {refreshing ? 'Actualizando…' : '↻ Actualizar precios'}
      </button>
    </div>
  );
}

function ProductsCard({
  data,
  onAdd,
  onEdit,
}: {
  data: Data;
  onAdd: () => void;
  onEdit: (product: Product) => void;
}) {
  const priceOf = new Map(data.prices.products.map((p) => [p.product_id, p]));
  return (
    <section className="card panel">
      <div className="between">
        <h2>Productos</h2>
        <button type="button" className="btn btn-sm" onClick={onAdd}>
          + Añadir producto
        </button>
      </div>
      {data.products.length === 0 ? (
        <p className="muted">
          Añade los productos que tienes (por ISIN o con su símbolo de Xetra) antes de apuntar
          compras.
        </p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ minWidth: 640 }}>
            <thead>
              <tr>
                <th>Producto</th>
                <th>Tipo</th>
                <th className="r">Último precio</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {data.products.map((p) => {
                const price = priceOf.get(p.id);
                return (
                  <tr key={p.id}>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <strong>{p.name}</strong>
                        <span className="muted" style={{ fontSize: 12 }}>
                          {[p.isin, p.source_id].filter(Boolean).join(' · ') || 'Valor a mano'}
                        </span>
                      </div>
                    </td>
                    <td className="muted">{kindLabel(p.kind)}</td>
                    <td className="r" style={{ whiteSpace: 'nowrap' }}>
                      {p.price_source === 'manual' ? (
                        <span className="muted">Valor anotado a mano</span>
                      ) : price?.price && price.currency && price.date ? (
                        <>
                          <span className="tnum">{formatPrice(price.price, price.currency)}</span>{' '}
                          <span className="muted" style={{ fontSize: 12 }}>
                            {formatDate(price.date)}
                          </span>
                          {price.stale && (
                            <>
                              {' '}
                              <span className="badge" style={STALE_BADGE}>
                                Desactualizado
                              </span>
                            </>
                          )}
                        </>
                      ) : (
                        <span className="muted">Sin precio todavía</span>
                      )}
                    </td>
                    <td className="r">
                      <button type="button" className="link-btn" onClick={() => onEdit(p)}>
                        Editar
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

const FIRST_OPERATIONS = 10;

function OperationsCard({ data, onOpen }: { data: Data; onOpen: (mode: OperationMode) => void }) {
  const [showAll, setShowAll] = useState(false);
  const canAdd = data.products.length > 0;
  const shown = showAll ? data.operations : data.operations.slice(0, FIRST_OPERATIONS);
  return (
    <section className="card panel">
      <div className="between">
        <h2>Operaciones</h2>
        <button
          type="button"
          className="btn btn-sm"
          style={{ minHeight: 40 }}
          onClick={() => onOpen({ kind: 'new' })}
          disabled={!canAdd}
          title={canAdd ? undefined : 'Añade antes un producto'}
        >
          + Añadir operación
        </button>
      </div>
      {data.operations.length === 0 ? (
        <p className="muted">
          {canAdd
            ? 'Todavía no has apuntado ninguna operación.'
            : 'Cuando tengas productos, aquí apuntarás tus compras, ventas y dividendos.'}
        </p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ minWidth: 760 }}>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Producto</th>
                <th>Cuenta</th>
                <th>Tipo</th>
                <th className="r">Participaciones</th>
                <th className="r">Importe</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {shown.map((op) => (
                <tr key={op.id}>
                  <td className="tnum">{formatDate(op.date)}</td>
                  <td>
                    <strong>{op.product_name}</strong>
                  </td>
                  <td className="muted">{op.account_name}</td>
                  <td>{operationLabel(op.kind)}</td>
                  <td className="r tnum">
                    {Number(op.shares) > 0 ? formatShares(op.shares) : '—'}
                  </td>
                  <td className="r tnum" style={{ fontWeight: 700 }}>
                    {formatEur(op.amount_eur)}
                  </td>
                  <td className="r" style={{ whiteSpace: 'nowrap' }}>
                    <button
                      type="button"
                      className="link-btn"
                      onClick={() => onOpen({ kind: 'duplicate', op })}
                    >
                      Duplicar
                    </button>{' '}
                    ·{' '}
                    <button
                      type="button"
                      className="link-btn"
                      onClick={() => onOpen({ kind: 'edit', op })}
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
      {data.operations.length > FIRST_OPERATIONS && (
        <button
          type="button"
          className="link-btn"
          style={{ alignSelf: 'flex-start' }}
          onClick={() => setShowAll(!showAll)}
        >
          {showAll
            ? `Ver solo las ${FIRST_OPERATIONS} últimas`
            : `Ver las ${data.operations.length} operaciones`}
        </button>
      )}
    </section>
  );
}
