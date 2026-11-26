import type { Transaction } from '../api';

// Colores de la maqueta (BADGES)
const BADGES = {
  auto: ['Auto', 'var(--good-bg)', 'var(--good)'],
  review: ['Revisar', 'var(--warn-bg)', 'var(--warn)'],
  manual: ['Manual', 'var(--purple-bg)', 'var(--purple)'],
  internal: ['Interna', 'var(--soft)', 'var(--neutral)'],
} as const;

function statusOf(tx: Transaction): keyof typeof BADGES {
  return tx.is_internal_transfer ? 'internal' : tx.category_status;
}

export function StatusBadge({ tx }: { tx: Transaction }) {
  const [label, background, color] = BADGES[statusOf(tx)];
  return (
    <span className="badge" style={{ background, color }}>
      {label}
    </span>
  );
}
