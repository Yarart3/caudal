import { useNavigate } from 'react-router';
import { api, type NetWorth, type ProductKind } from '../api';
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

/** Pestaña Patrimonio (DISENO 3.1): liquidez de cada cuenta e inversiones (Fase 3, parte 3.6). */
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
              hint={liquidityHint(data)}
              color="#0B5747"
            />
            <Kpi
              label="Inversiones"
              value={formatEurRounded(data.investments)}
              hint={
                Number(data.investments) > 0
                  ? `${formatSignedRounded(data.investments_gain)} de plusvalía`
                  : 'Sin inversiones todavía'
              }
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
              <TypeDonut data={data} />
            </div>
            <GoalCard month={month} />
          </section>
        </>
      )}
    </AppShell>
  );
}

function liquidityHint(data: NetWorth): string {
  const count = data.accounts.filter((a) => a.kind !== 'investment').length;
  return `${count} ${count === 1 ? 'cuenta' : 'cuentas'} con dinero disponible`;
}

// Tipos de inversión del reparto (colores de la maqueta para ETFs y cripto)
const INVESTMENT_SLICES: { kind: ProductKind; label: string; color: string }[] = [
  { kind: 'etf', label: 'ETFs', color: '#3555A0' },
  { kind: 'stock', label: 'Acciones', color: '#28437F' },
  { kind: 'fund', label: 'Fondos', color: '#5B76B8' },
  { kind: 'crypto', label: 'Cripto', color: '#B08A12' },
  { kind: 'pension', label: 'Planes de pensiones', color: '#7A5AA6' },
  { kind: 'commodity', label: 'Materias primas', color: '#8A6D1E' },
  { kind: 'other', label: 'Otras inversiones', color: '#8C939C' },
];

function TypeDonut({ data }: { data: NetWorth }) {
  const slices: Slice[] = [
    ...INVESTMENT_SLICES.map((s) => ({
      label: s.label,
      amount: data.investments_by_kind[s.kind] ?? '0',
      color: s.color,
    })),
    { label: 'Fondo monetario', amount: data.by_type.money_market ?? '0', color: '#0E6B58' },
    { label: 'Efectivo', amount: data.by_type.cash ?? '0', color: '#9DB8AE' },
  ].filter((s) => Number(s.amount) > 0);
  if (slices.length === 0) return <p className="muted">Ahora mismo no tienes saldo positivo.</p>;
  return <Donut label="Reparto del patrimonio por tipo" slices={slices} size={140} />;
}
