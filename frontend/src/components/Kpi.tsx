/** Tarjeta de indicador: etiqueta, cifra grande y una línea de explicación (maqueta). */
export function Kpi({
  label,
  value,
  hint,
  color = 'var(--ink)',
}: {
  label: string;
  value: string;
  hint: string;
  color?: string;
}) {
  return (
    <div className="card panel kpi">
      <span className="muted kpi-label">{label}</span>
      <span className="num kpi-value" style={{ color }}>
        {value}
      </span>
      <span className="muted kpi-hint">{hint}</span>
    </div>
  );
}
