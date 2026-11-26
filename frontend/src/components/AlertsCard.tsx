import { api, type AlertLevel } from '../api';
import { useDashboard } from '../hooks/useDashboard';

const loadAlerts = (month?: string) => api.alerts(month);

const COLORS: Record<AlertLevel, { background: string; color: string }> = {
  danger: { background: 'var(--danger-bg)', color: 'var(--bad)' },
  warning: { background: 'var(--warn-bg)', color: 'var(--warn)' },
  positive: { background: 'var(--good-bg2)', color: 'var(--good)' },
  info: { background: 'var(--info-bg)', color: 'var(--info)' },
};

/** Avisos del mes (DISENO 9.5): presupuestos superados, gasto alto, cambios y recurrentes. */
export function AlertsCard({ month }: { month?: string }) {
  const { data, error } = useDashboard(loadAlerts, month);

  return (
    <div className="card panel">
      <h2>Avisos</h2>
      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      {!data && !error && <p className="muted">Cargando…</p>}
      {data && data.items.length === 0 && (
        <p className="muted">Sin avisos este mes. Todo en orden.</p>
      )}
      {data?.items.map((alert, index) => (
        <div
          key={`${alert.kind}-${alert.category_id ?? index}`}
          className="alert-row"
          style={COLORS[alert.level]}
        >
          <strong style={{ color: COLORS[alert.level].color, whiteSpace: 'nowrap' }}>
            {alert.title}
          </strong>
          <span style={{ color: 'var(--ink)' }}>{alert.message}</span>
        </div>
      ))}
    </div>
  );
}
