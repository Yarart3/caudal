import { addMonths, formatMonth, recentMonths } from '../format';

const LATEST = recentMonths(1)[0];

/** Selector de mes con flechas: ‹ Septiembre 2026 ›. `month` es "AAAA-MM". */
export function MonthSelect({
  month,
  onChange,
}: {
  month: string;
  onChange: (month: string) => void;
}) {
  const options = recentMonths(24);
  if (!options.includes(month)) options.push(month);
  options.sort().reverse();
  const oldest = options[options.length - 1];

  return (
    <div className="row month-select" role="group" aria-label="Mes">
      <button
        type="button"
        className="btn btn-sm"
        aria-label="Mes anterior"
        disabled={month <= oldest}
        onClick={() => onChange(addMonths(month, -1))}
      >
        ‹
      </button>
      <select aria-label="Elegir mes" value={month} onChange={(e) => onChange(e.target.value)}>
        {options.map((m) => (
          <option key={m} value={m}>
            {formatMonth(m)}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="btn btn-sm"
        aria-label="Mes siguiente"
        disabled={month >= LATEST}
        onClick={() => onChange(addMonths(month, 1))}
      >
        ›
      </button>
    </div>
  );
}
