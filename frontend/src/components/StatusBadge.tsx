import type { Transaction } from '../api';

// Colores de la maqueta (BADGES)
const BADGES = {
  auto: ['Auto', '#E3F0EA', '#0B5747'],
  review: ['Revisar', '#FBEBDD', '#8A3A0C'],
  manual: ['Manual', '#EEE6F0', '#62305F'],
  internal: ['Interna', '#EEF0EC', '#4A5059'],
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
