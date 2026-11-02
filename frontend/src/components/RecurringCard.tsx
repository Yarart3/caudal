import { api } from '../api';
import { formatDate, formatEur } from '../format';
import { useDashboard } from '../hooks/useDashboard';

const loadRecurring = (month?: string) => api.recurring(month);

/** Pagos recurrentes detectados en los extractos (DISENO 8.4): suscripciones, recibos, seguros… */
export function RecurringCard({ month }: { month?: string }) {
  const { data, error } = useDashboard(loadRecurring, month);

  return (
    <div className="card panel">
      <div className="between">
        <h2>Pagos recurrentes</h2>
        {data && data.items.length > 0 && (
          <span className="muted" style={{ fontSize: 13 }}>
            {formatEur(data.monthly_total)}/mes
          </span>
        )}
      </div>
      <span className="muted" style={{ fontSize: 13 }}>
        Detectados automáticamente en tus extractos
      </span>
      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      {!data && !error && <p className="muted">Cargando…</p>}
      {data && data.items.length === 0 && (
        <p className="muted">
          Todavía no se ha detectado ningún pago que se repita. Hacen falta al menos 3 meses
          seguidos de un mismo cobro (2 años para los anuales).
        </p>
      )}
      {data?.items.map((item) => (
        <div className="list-row" key={item.key}>
          <span>
            <strong>{item.description}</strong>{' '}
            {item.is_new && (
              <span className="badge" style={{ background: '#EEF2FA', color: '#28437F' }}>
                Nuevo
              </span>
            )}{' '}
            <span className="muted">
              · {item.category_name} · {item.account_name} ·{' '}
              {item.frequency === 'monthly' ? 'mensual' : 'anual'} · próximo{' '}
              {formatDate(item.next_date)}
            </span>
          </span>
          <span className="num" style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>
            {formatEur(item.amount)}
            {item.frequency === 'annual' ? '/año' : ''}
          </span>
        </div>
      ))}
    </div>
  );
}
