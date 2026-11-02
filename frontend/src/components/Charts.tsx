import type { ReactNode } from 'react';
import type { AccountBalance, CashflowMonth, NetWorthMonth } from '../api';
import { formatEur, formatEurRounded, formatMonth, formatMonthShort } from '../format';

// Gráficos en CSS, como la maqueta (DISENO §2 y §10): una barra es un div con la altura
// proporcional al máximo y el donut es un conic-gradient. Los importes llegan como texto y solo
// se pasan a Number para calcular el dibujo; las cifras que se leen salen tal cual de la API.

const BAR_HEIGHT = 180;
const STACK_HEIGHT = 190;

const toNumber = (amount: string) => Math.max(0, Number(amount));
const height = (value: number, max: number, full: number) =>
  max > 0 ? Math.round((value / max) * full) : 0;

function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="row muted legend">
      {items.map((item) => (
        <span key={item.label} className="row" style={{ gap: 6 }}>
          <span className="dot" style={{ background: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}

/** Ingresos vs gastos, 12 meses (pestaña Movimientos). El último es el mes elegido. */
export function IncomeExpenseChart({ history }: { history: CashflowMonth[] }) {
  const max = Math.max(...history.flatMap((m) => [toNumber(m.income), toNumber(m.expense)]), 0);
  const last = history.length - 1;
  return (
    <div className="card panel">
      <div className="between">
        <h2>Ingresos vs gastos · 12 meses</h2>
        <Legend
          items={[
            { label: 'Ingresos', color: 'var(--accent)' },
            { label: 'Gastos', color: 'var(--exp)' },
          ]}
        />
      </div>
      <div className="bars" role="img" aria-label="Ingresos y gastos de los últimos 12 meses">
        {history.map((m, i) => (
          <div
            key={m.month}
            className="bar-col"
            title={`${formatMonth(m.month)}: ingresos ${formatEur(m.income)} · gastos ${formatEur(m.expense)}`}
          >
            <div className="bar-pair">
              <div
                style={{
                  height: Math.max(2, height(toNumber(m.income), max, BAR_HEIGHT)),
                  background: 'var(--accent)',
                }}
              />
              <div
                style={{
                  height: Math.max(2, height(toNumber(m.expense), max, BAR_HEIGHT)),
                  background: 'var(--exp)',
                }}
              />
            </div>
            <span className={i === last ? 'bar-label on' : 'bar-label'}>
              {formatMonthShort(m.month)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Evolución del patrimonio, 12 meses: barras apiladas inversiones + liquidez. */
export function NetWorthChart({ history }: { history: NetWorthMonth[] }) {
  const totals = history.map((m) => toNumber(m.investments) + toNumber(m.liquidity));
  const max = Math.max(...totals, 0);
  const last = history.length - 1;
  return (
    <div className="card panel">
      <div className="between">
        <h2>Evolución del patrimonio · 12 meses</h2>
        <Legend
          items={[
            { label: 'Inversiones', color: 'var(--inv)' },
            { label: 'Liquidez', color: 'var(--liq)' },
          ]}
        />
      </div>
      <div
        className="bars"
        style={{ gap: 8 }}
        role="img"
        aria-label="Patrimonio a final de cada uno de los últimos 12 meses"
      >
        {history.map((m, i) => (
          <div
            key={m.month}
            className="bar-col"
            title={`${formatMonth(m.month)}: inversiones ${formatEur(m.investments)} · liquidez ${formatEur(m.liquidity)}`}
          >
            <div className="stackbar">
              <div
                style={{
                  height: height(toNumber(m.investments), max, STACK_HEIGHT),
                  background: 'var(--inv)',
                  borderRadius: '3px 3px 0 0',
                }}
              />
              <div
                style={{
                  height: height(toNumber(m.liquidity), max, STACK_HEIGHT),
                  background: 'var(--liq)',
                }}
              />
            </div>
            <span className={i === last ? 'bar-label on' : 'bar-label'}>
              {formatMonthShort(m.month)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export type Slice = { label: string; amount: string; color: string };

/** Donut con su leyenda y el porcentaje de cada porción. `center` va dentro del círculo. */
export function Donut({
  slices,
  label,
  size = 168,
  center,
}: {
  slices: Slice[];
  label: string;
  size?: number;
  center?: ReactNode;
}) {
  const values = slices.map((s) => toNumber(s.amount));
  const total = values.reduce((a, b) => a + b, 0);
  let start = 0;
  const stops = slices.map((s, i) => {
    const end = start + (total > 0 ? (values[i] / total) * 100 : 0);
    const stop = `${s.color} ${start.toFixed(2)}% ${end.toFixed(2)}%`;
    start = end;
    return stop;
  });
  const inner = Math.round(size * 0.62);
  return (
    <div className="row" style={{ flexWrap: 'wrap', gap: 20 }}>
      <div
        className="donut"
        role="img"
        aria-label={label}
        style={{
          width: size,
          height: size,
          background: total > 0 ? `conic-gradient(${stops.join(', ')})` : 'var(--soft)',
        }}
      >
        <div className="donut-in" style={{ width: inner, height: inner }}>
          {center}
        </div>
      </div>
      <ul className="donut-legend">
        {slices.map((s, i) => (
          <li key={s.label} className="row" title={formatEur(s.amount)}>
            <span className="dot" style={{ background: s.color }} />
            <span style={{ flex: 1 }}>{s.label}</span>
            <span className="muted tnum">
              {total > 0 ? `${Math.round((values[i] / total) * 100)} %` : '—'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const LIQUIDITY_LABEL: Record<AccountBalance['liquidity_type'], string> = {
  cash: 'Efectivo',
  money_market: 'Fondo monetario',
};

/** Patrimonio por entidad (cada cuenta). Hasta la Fase 3, todo es liquidez. */
export function EntityBars({ accounts }: { accounts: AccountBalance[] }) {
  const sorted = [...accounts].sort((a, b) => Number(b.balance) - Number(a.balance));
  const max = Math.max(...sorted.map((a) => toNumber(a.balance)), 0);
  return (
    <div className="card panel">
      <h2>Patrimonio por entidad</h2>
      {sorted.length === 0 ? (
        <p className="muted">Todavía no tienes cuentas.</p>
      ) : (
        sorted.map((a) => (
          <div key={a.id} className="entity">
            <div className="between" style={{ fontSize: 14, gap: 8 }}>
              <span>
                <strong>{a.name}</strong>{' '}
                <span className="muted">· {LIQUIDITY_LABEL[a.liquidity_type]}</span>
              </span>
              <strong className="tnum">{formatEurRounded(a.balance)}</strong>
            </div>
            <div className="track" style={{ height: 10 }}>
              <div
                style={{
                  width: `${max > 0 ? ((toNumber(a.balance) / max) * 100).toFixed(1) : 0}%`,
                  background: 'var(--liq)',
                }}
              />
            </div>
          </div>
        ))
      )}
      <span className="muted" style={{ fontSize: 12 }}>
        Azul = invertido · Verde = efectivo / disponible
      </span>
    </div>
  );
}
