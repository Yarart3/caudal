import { useNavigate } from 'react-router';
import { api } from '../api';
import { AppShell } from '../AppShell';
import { useAuth } from '../auth/AuthContext';
import { Donut, EntityBars, NetWorthChart, type Slice } from '../components/Charts';
import { GoalCard } from '../components/GoalCard';
import { Kpi } from '../components/Kpi';
import { MonthSelect } from '../components/MonthSelect';
import { formatEurRounded, formatSignedRounded, monthName } from '../format';
import { useDashboard } from '../hooks/useDashboard';
import { useMonthParam } from '../hooks/useMonthParam';

const loadNetWorth = (month?: string) => api.netWorth(month);

/** Pestaña Patrimonio (DISENO 3.1). Hasta la Fase 3 solo hay liquidez: saldo de cada cuenta. */
export function PanelPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [month, setMonth] = useMonthParam();
  const { data, error } = useDashboard(loadNetWorth, month);

  return (
    <AppShell title="Patrimonio" current="Patrimonio" tabs>
      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      {!data && !error && <p className="muted">Cargando…</p>}

      {data && data.accounts.length === 0 && (
        <section className="card empty">
          <h2>Tu patrimonio</h2>
          <p className="muted">
            Hola, {user?.display_name}. Aquí verás cuánto tienes y cómo evoluciona. Solo tú puedes
            ver lo que hay en tu panel.
          </p>
          <p className="muted">Empieza importando el extracto de una de tus cuentas.</p>
          <div className="row" style={{ flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => navigate('/movimientos/importar')}
            >
              Importar extracto
            </button>
            <button type="button" className="btn" onClick={() => navigate('/movimientos')}>
              Ver movimientos
            </button>
          </div>
        </section>
      )}

      {data && data.accounts.length > 0 && (
        <>
          <MonthSelect month={data.month} onChange={setMonth} />
          <section className="k4">
            <Kpi
              label="Patrimonio neto"
              value={formatEurRounded(data.net_worth)}
              hint="Todo lo que tienes, sumado"
            />
            <Kpi
              label="Liquidez"
              value={formatEurRounded(data.liquidity)}
              hint={`${data.accounts.length} ${data.accounts.length === 1 ? 'cuenta' : 'cuentas'} con dinero disponible`}
              color="#0B5747"
            />
            <Kpi
              label="Inversiones"
              value={formatEurRounded(data.investments)}
              hint="Sin inversiones todavía"
              color="#28437F"
            />
            <Kpi
              label="Ahorro este mes"
              value={formatSignedRounded(data.savings)}
              hint={`Ingresos − gastos de ${monthName(data.month)}`}
              color={Number(data.savings) >= 0 ? '#0B5747' : 'var(--bad)'}
            />
          </section>

          <section className="r2">
            <NetWorthChart history={data.history} />
            <EntityBars accounts={data.accounts} />
          </section>

          <section className="r2e">
            <div className="card panel">
              <h2>Reparto por tipo</h2>
              <TypeDonut byType={data.by_type} />
            </div>
            <GoalCard month={month} />
          </section>
        </>
      )}
    </AppShell>
  );
}

function TypeDonut({ byType }: { byType: Record<string, string> }) {
  const slices: Slice[] = [
    { label: 'Fondo monetario', amount: byType.money_market ?? '0', color: '#0E6B58' },
    { label: 'Efectivo', amount: byType.cash ?? '0', color: '#9DB8AE' },
  ].filter((s) => Number(s.amount) > 0);
  if (slices.length === 0) return <p className="muted">Ahora mismo no tienes saldo positivo.</p>;
  return <Donut label="Reparto del patrimonio por tipo" slices={slices} size={140} />;
}
