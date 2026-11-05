import type { Benchmark, InvestmentSummary, Operation, Position, Positions } from '../api';
import {
  formatDate,
  formatEur,
  formatEurRounded,
  formatMonth,
  formatMonthYearShort,
  formatPercent,
  formatPrice,
  formatShares,
  formatSignedRounded,
} from '../format';
import { kindLabel } from '../investmentLabels';
import { Kpi } from './Kpi';

const GOOD = '#0B5747';
const WARN = '#8A3A0C';
const TAGS = {
  delay: { text: '~15 min', background: '#EEF0EC', color: '#4A5059' },
  close: { text: 'Cierre', background: '#E4E9F5', color: '#28437F' },
  manual: { text: 'A mano', background: '#EEF0EC', color: '#4A5059' },
  stale: { text: 'Desactualizado', background: '#FBE6D4', color: WARN },
};

const signColor = (amount: string) => (Number(amount) >= 0 ? GOOD : 'var(--bad)');
const months = (count: number) => `${count} ${count === 1 ? 'mes seguido' : 'meses seguidos'}`;

/**
 * Lo de arriba de la pestaña Inversiones (Fase 3, parte 3.5), como en la maqueta: indicadores,
 * «Mis posiciones», aportaciones, comparativa con un indexado, dividendos y, debajo,
 * rentabilidad por año y costes. Solo enseña datos: no da recomendaciones.
 */
export function PortfolioOverview({
  summary,
  positions,
  benchmark,
  operations,
  onAddOperation,
}: {
  summary: InvestmentSummary;
  positions: Positions;
  benchmark: Benchmark;
  operations: Operation[];
  onAddOperation: () => void;
}) {
  const s = summary;
  return (
    <>
      {s.missing_prices.length > 0 && (
        <p className="err" role="status">
          Sin precio de hoy para {s.missing_prices.join(', ')}: no cuenta{' '}
          {s.missing_prices.length === 1 ? 'en el valor' : 'n en el valor'} ni en la plusvalía.
          Prueba a actualizar los precios.
        </p>
      )}
      <section className="k4">
        <Kpi
          label="Valor de las inversiones"
          value={formatEurRounded(s.value)}
          hint={`Invertido: ${formatEurRounded(s.cost)}`}
          color="var(--inv)"
        />
        <Kpi
          label="Plusvalía"
          value={formatSignedRounded(s.gain)}
          hint={
            s.gain_pct === null
              ? 'De lo que aún tienes'
              : `${formatPercent(s.gain_pct, { signed: true })} sobre lo invertido`
          }
          color={signColor(s.gain)}
        />
        <Kpi
          label="Rentabilidad anual (TIR)"
          value={s.xirr === null ? '—' : formatPercent(s.xirr, { signed: true })}
          hint="Tiene en cuenta cuándo aportaste"
        />
        <Kpi
          label="Aportado en 12 meses"
          value={formatEurRounded(s.contributed_12m)}
          hint={s.streak > 0 ? `Racha: ${months(s.streak)}` : 'Compras menos ventas'}
        />
      </section>

      <PositionsCard positions={positions} asOf={s.as_of} onAdd={onAddOperation} />

      <section className="r3">
        <ContributionsCard summary={s} />
        <BenchmarkCard benchmark={benchmark} />
        <DividendsCard summary={s} operations={operations} />
      </section>

      <section className="r2h">
        <YearReturnsCard summary={s} />
        <CostsCard summary={s} />
      </section>

      <p className="muted" style={{ fontSize: 12, margin: 0 }}>
        Caudal muestra datos, no da recomendaciones de compra o venta ni es asesoramiento
        financiero. Los precios son de fuentes gratuitas y pueden diferir de los del broker.
      </p>
    </>
  );
}

function PositionsCard({
  positions,
  asOf,
  onAdd,
}: {
  positions: Positions;
  asOf: string;
  onAdd: () => void;
}) {
  return (
    <section className="card panel">
      <div className="between">
        <h2>Mis posiciones</h2>
        <button type="button" className="btn btn-sm" style={{ minHeight: 40 }} onClick={onAdd}>
          + Añadir compra / venta
        </button>
      </div>
      {positions.items.length === 0 ? (
        <p className="muted">Ahora mismo no tienes participaciones de ningún producto.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ minWidth: 860 }}>
            <thead>
              <tr>
                <th>Producto</th>
                <th>Broker</th>
                <th className="r">Participaciones</th>
                <th className="r">Precio medio</th>
                <th className="r">Precio actual</th>
                <th className="r">Valor</th>
                <th className="r">Plusvalía</th>
                <th className="r">Peso</th>
              </tr>
            </thead>
            <tbody>
              {positions.items.map((p) => (
                <PositionRow key={p.product_id} p={p} asOf={asOf} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function PositionRow({ p, asOf }: { p: Position; asOf: string }) {
  const manual = p.price === null && p.value !== null;
  const tag = p.stale
    ? TAGS.stale
    : manual
      ? TAGS.manual
      : p.price_date === asOf
        ? TAGS.delay
        : TAGS.close;
  const tagTitle =
    p.price_date === null
      ? undefined
      : `Precio del ${formatDate(p.price_date)}${p.stale ? ' (no se ha podido actualizar)' : ''}`;
  return (
    <tr>
      <td>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <strong>{p.name}</strong>
          <span className="muted" style={{ fontSize: 12 }}>
            {[p.isin ?? p.symbol, kindLabel(p.kind)].filter(Boolean).join(' · ')}
          </span>
        </div>
      </td>
      <td className="muted">{p.accounts.join(' · ')}</td>
      <td className="r tnum">{formatShares(p.shares)}</td>
      <td className="r tnum muted">
        {p.average_price === null ? '—' : formatPrice(p.average_price, 'EUR')}
      </td>
      <td className="r" style={{ whiteSpace: 'nowrap' }}>
        {p.price !== null && p.price_currency !== null ? (
          <span className="tnum">{formatPrice(p.price, p.price_currency)}</span>
        ) : (
          !manual && <span className="muted">Sin precio</span>
        )}{' '}
        {(p.price !== null || manual) && (
          <span
            className="badge"
            style={{ background: tag.background, color: tag.color }}
            title={tagTitle}
          >
            {tag.text}
          </span>
        )}
      </td>
      <td className="r tnum" style={{ fontWeight: 700 }}>
        {p.value === null ? '—' : formatEur(p.value)}
      </td>
      <td
        className="r tnum"
        style={{
          fontWeight: 700,
          whiteSpace: 'nowrap',
          color: p.gain === null ? undefined : signColor(p.gain),
        }}
      >
        {p.gain === null
          ? '—'
          : `${Number(p.gain) > 0 ? '+' : ''}${formatEur(p.gain)}${
              p.gain_pct === null ? '' : ` · ${formatPercent(p.gain_pct, { signed: true })}`
            }`}
      </td>
      <td className="r muted" style={{ whiteSpace: 'nowrap' }}>
        {p.weight === null ? '—' : formatPercent(p.weight, { digits: 0 })}
      </td>
    </tr>
  );
}

function ContributionsCard({ summary }: { summary: InvestmentSummary }) {
  const items = summary.contributions;
  const max = Math.max(...items.map((m) => Number(m.amount)), 0);
  return (
    <div className="card panel">
      <div className="between">
        <h2>Aportaciones</h2>
        <span className="muted" style={{ fontSize: 13 }}>
          {formatEurRounded(summary.contributed_12m)} en 12 meses
        </span>
      </div>
      <div
        className="contrib-bars"
        role="img"
        aria-label="Aportación neta de cada uno de los últimos 12 meses"
      >
        {items.map((m) => {
          const amount = Number(m.amount);
          return (
            <div
              key={m.month}
              title={`${formatMonth(m.month)}: ${formatEur(m.amount)}`}
              style={{ height: max > 0 && amount > 0 ? Math.max(2, (amount / max) * 120) : 0 }}
            />
          );
        })}
      </div>
      <div className="between muted" style={{ fontSize: 12 }}>
        <span>{formatMonthYearShort(items[0].month)}</span>
        <span>{formatMonthYearShort(items[items.length - 1].month)}</span>
      </div>
      <span className="muted" style={{ fontSize: 13 }}>
        {summary.streak > 0 ? (
          <>
            Racha: <strong style={{ color: 'var(--ink)' }}>{months(summary.streak)}</strong>{' '}
            aportando
          </>
        ) : (
          'Cada barra es lo comprado menos lo vendido ese mes.'
        )}
      </span>
    </div>
  );
}

function BenchmarkCard({ benchmark }: { benchmark: Benchmark }) {
  return (
    <div className="card panel" style={{ gap: 12 }}>
      <h2>¿Y si todo fuera a un indexado?</h2>
      <span className="muted" style={{ fontSize: 13 }}>
        Mismas compras y ventas, mismas fechas
      </span>
      <div className="list-row">
        <span style={{ fontWeight: 700 }}>Mi cartera</span>
        <span className="tnum">
          <strong>{formatEurRounded(benchmark.value)}</strong>
        </span>
      </div>
      {benchmark.items.map((b) => (
        <div
          className="list-row"
          key={b.key}
          title={b.xirr === null ? undefined : `TIR: ${formatPercent(b.xirr, { signed: true })}`}
        >
          <span>{b.name}</span>
          {b.available && b.value !== null && b.diff !== null ? (
            <span className="tnum" style={{ whiteSpace: 'nowrap' }}>
              <strong>{formatEurRounded(b.value)}</strong>{' '}
              <span style={{ fontSize: 13, color: Number(b.diff) > 0 ? WARN : GOOD }}>
                {formatSignedRounded(b.diff)}
              </span>
            </span>
          ) : (
            <span className="muted" style={{ fontSize: 13 }}>
              Sin datos
            </span>
          )}
        </div>
      ))}
      {benchmark.xirr !== null && (
        <span className="muted" style={{ fontSize: 12 }}>
          Tu TIR: {formatPercent(benchmark.xirr, { signed: true })}. Pasa el ratón por cada índice
          para ver la suya.
        </span>
      )}
    </div>
  );
}

function DividendsCard({
  summary,
  operations,
}: {
  summary: InvestmentSummary;
  operations: Operation[];
}) {
  const dividends = operations.filter((op) => op.kind === 'dividend').slice(0, 5);
  return (
    <div className="card panel" style={{ gap: 10 }}>
      <div className="between">
        <h2>Dividendos</h2>
        <span className="muted" style={{ fontSize: 13 }}>
          {formatEur(summary.dividends_12m)} en 12 meses
        </span>
      </div>
      {dividends.length === 0 ? (
        <p className="muted" style={{ margin: 0 }}>
          Todavía no has apuntado dividendos. Los de tus ETF de acumulación se reinvierten solos.
        </p>
      ) : (
        dividends.map((op) => (
          <div className="list-row" key={op.id}>
            <span>
              <strong>{op.product_name}</strong>{' '}
              <span className="muted">· {formatDate(op.date)}</span>
            </span>
            <span className="tnum" style={{ fontWeight: 700, color: GOOD, whiteSpace: 'nowrap' }}>
              +{formatEur(op.amount_eur)}
            </span>
          </div>
        ))
      )}
    </div>
  );
}

function YearReturnsCard({ summary }: { summary: InvestmentSummary }) {
  const years = [...summary.year_returns].reverse();
  const thisYear = summary.as_of.slice(0, 4);
  return (
    <div className="card panel" style={{ gap: 10 }}>
      <h2>Rentabilidad por año</h2>
      {years.length === 0 ? (
        <p className="muted" style={{ margin: 0 }}>
          Aparecerá cuando haya precios desde tu primera compra.
        </p>
      ) : (
        years.map((y) => (
          <div className="list-row" key={y.year}>
            <span>
              {y.year}
              {String(y.year) === thisYear && <span className="muted"> · hasta hoy</span>}
            </span>
            <span className="tnum" style={{ fontWeight: 700, color: signColor(y.return_pct) }}>
              {formatPercent(y.return_pct, { signed: true })}
            </span>
          </div>
        ))
      )}
      <span className="muted" style={{ fontSize: 12 }}>
        Sin contar lo que aportaste ese año (método Dietz modificado).
      </span>
    </div>
  );
}

function CostsCard({ summary }: { summary: InvestmentSummary }) {
  const rows: [string, string, string?][] = [
    [
      'Peor caída',
      summary.max_drawdown === null ? '—' : formatPercent(summary.max_drawdown),
      'Lo máximo que llegó a bajar desde un máximo, sin contar aportaciones',
    ],
    ['Plusvalía realizada', formatSignedRounded(summary.realized), 'De lo que ya vendiste (FIFO)'],
    ['Dividendos cobrados', formatEur(summary.dividends), 'Desde el principio'],
    [
      'Comisiones de los fondos',
      `${formatEur(summary.ter_annual)} al año`,
      'Valor de hoy × TER de cada producto (estimado)',
    ],
    ['Otras comisiones pagadas', formatEur(summary.fees), 'Las apuntadas como «Comisión»'],
  ];
  return (
    <div className="card panel" style={{ gap: 10 }}>
      <h2>Riesgo y costes</h2>
      {rows.map(([label, value, help]) => (
        <div className="list-row" key={label} title={help}>
          <span>{label}</span>
          <span className="tnum" style={{ fontWeight: 700, whiteSpace: 'nowrap' }}>
            {value}
          </span>
        </div>
      ))}
    </div>
  );
}
