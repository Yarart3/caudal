import type { Category } from '../api';

/**
 * Desplegable de categorías agrupadas en Gastos e Ingresos. `value` null = la opción vacía
 * (`emptyLabel`), por ejemplo «Sin categoría (por revisar)».
 */
export function CategorySelect({
  id,
  categories,
  value,
  onChange,
  emptyLabel,
  disabled,
  ariaLabel,
}: {
  id?: string;
  categories: Category[];
  value: number | null;
  onChange: (value: number | null) => void;
  emptyLabel: string;
  disabled?: boolean;
  ariaLabel?: string;
}) {
  const groups = [
    { label: 'Gastos', items: categories.filter((c) => c.kind === 'expense') },
    { label: 'Ingresos', items: categories.filter((c) => c.kind === 'income') },
  ];
  return (
    <select
      id={id}
      aria-label={ariaLabel}
      value={value ?? ''}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
    >
      <option value="">{emptyLabel}</option>
      {groups.map(
        (group) =>
          group.items.length > 0 && (
            <optgroup key={group.label} label={group.label}>
              {group.items.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </optgroup>
          ),
      )}
    </select>
  );
}
