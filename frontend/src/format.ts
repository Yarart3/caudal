// Formatos españoles para la pantalla. El dinero llega como texto ("-1234.50") y se formatea
// sin pasar por cálculos con float.

const eur = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
  // es-ES no agrupa los miles en números de 4 cifras ("1234 €"): se fuerza "1.234 €"
  useGrouping: 'always',
});

/** "-1234.5" → "-1.234,50 €" */
export function formatEur(amount: string): string {
  return eur.format(Number(amount));
}

/** "2026-09-29" → "29/09/2026" */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-');
  return `${day}/${month}/${year}`;
}

/** Fecha de hoy en hora local como "AAAA-MM-DD" (lo que usa <input type="date">). */
export function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/**
 * Importe escrito a la española ("12,50", "1.234,5", "3") → texto con punto ("12.50").
 * Devuelve null si no es un importe positivo con como mucho 2 decimales.
 */
export function parseEsAmount(text: string): string | null {
  const clean = text.trim().replace(/\s|€/g, '');
  const match = /^(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?$/.exec(clean);
  if (!match) return null;
  const integer = match[1].replace(/\./g, '');
  const decimals = (match[2] ?? '').padEnd(2, '0');
  if (/^0+$/.test(integer) && /^0+$/.test(decimals)) return null;
  return `${integer.replace(/^0+(?=\d)/, '')}.${decimals}`;
}
