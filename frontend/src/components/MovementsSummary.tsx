import { api } from '../api';
import { useDashboard } from '../hooks/useDashboard';
import { addMonths, formatEurRounded, monthName } from '../format';
import { Donut, IncomeExpenseChart } from './Charts';
import { Kpi } from './Kpi';

// Fuera del componente: useDashboard necesita una función estable
const loadCashflow = (month?: string) => api.cashflow(month);

/** Parte de arriba de Movimientos: 4 indicadores, ingresos vs gastos y gasto por categoría.
 * Sin transferencias internas (DISENO 9.1). */
export function MovementsSummary({ month }: { month?: string }) {
  const { data, error } = useDashboard(loadCashflow, month);

  if (error) {
    return (
      <p className="err" role="alert">
        {error}
      </p>
    );
  }
  if (!data) return <p className="muted">Cargando el resumen…</p>;

  const previous = monthName(addMonths(data.month, -1));
  const change = data.expense_change;
  return (
    <>
      <section className="k4">
        <Kpi
          label="Dinero en cuentas"
          value={formatEurRounded(data.cash_total)}
          hint="Liquidez disponible"
        />
        <Kpi
          label="Ingresos del mes"
          value={formatEurRounded(data.income)}
          hint={`Ingresos de ${monthName(data.month)}`}
          color="#0B5747"
        />
        <Kpi
          label="Gastos del mes"
          value={formatEurRounded(data.expense)}
          hint={
            change === null
              ? `Sin gastos en ${previous}`
              : `${change > 0 ? '+' : ''}${change} % vs ${previous}`
          }
          color="#A84A15"
        />
        <Kpi
          label="Tasa de ahorro"
          value={data.savings_rate === null ? '—' : `${data.savings_rate} %`}
          hint={`Ahorrado: ${formatEurRounded(data.savings)}`}
        />
      </section>
      <section className="r2">
        <IncomeExpenseChart history={data.history} />
        <div className="card panel">
          <h2>Gasto por categoría</h2>
          {data.by_category.length === 0 ? (
            <p className="muted">Sin gastos en {monthName(data.month)}.</p>
          ) : (
            <Donut
              label="Gasto por categoría"
              slices={data.by_category.map((c) => ({
                label: c.name,
                amount: c.amount,
                color: c.color,
              }))}
              center={
                <>
                  <span className="muted" style={{ fontSize: 12 }}>
                    Total
                  </span>
                  <span className="num" style={{ fontWeight: 700, fontSize: 18 }}>
                    {formatEurRounded(data.expense)}
                  </span>
                </>
              }
            />
          )}
        </div>
      </section>
    </>
  );
}
