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

const eurRounded = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
  minimumFractionDigits: 0,
  useGrouping: 'always',
});

/** "1234.56" → "1.235 €": sin céntimos, para los indicadores y los gráficos (como la maqueta). */
export function formatEurRounded(amount: string): string {
  return eurRounded.format(Number(amount));
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

/** "-12.5" → "-12,50 €" · "12.5" → "+12,50 €" (los ingresos llevan el +, como en la maqueta). */
export function formatSigned(amount: string): string {
  return Number(amount) > 0 ? `+${formatEur(amount)}` : formatEur(amount);
}

/** "-1234.50" → "1234,50": el importe sin signo, para rellenar un campo de texto. */
export function toEsAmount(amount: string): string {
  return amount.replace(/^-/, '').replace('.', ',');
}

const monthNames = new Intl.DateTimeFormat('es-ES', { month: 'long', year: 'numeric' });

/** "2026-09" → "Septiembre 2026" */
export function formatMonth(month: string): string {
  const [year, number] = month.split('-').map(Number);
  const text = monthNames.format(new Date(year, number - 1, 1)).replace(' de ', ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const monthLong = new Intl.DateTimeFormat('es-ES', { month: 'long' });

/** "2026-08" → "agosto" */
export function monthName(month: string): string {
  const [year, number] = month.split('-').map(Number);
  return monthLong.format(new Date(year, number - 1, 1));
}

/** "2026-09" → "Sep" (las tres primeras letras: Intl da «sept.» para septiembre). */
export function formatMonthShort(month: string): string {
  const name = monthName(month);
  return name.charAt(0).toUpperCase() + name.slice(1, 3);
}

/** "2026-01" y -1 → "2025-12": suma (o resta) meses a un "AAAA-MM". */
export function addMonths(month: string, count: number): string {
  const [year, number] = month.split('-').map(Number);
  const d = new Date(year, number - 1 + count, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

/** "120.4" → "+120 €" · "-35" → "-35 €": sin céntimos y con el + de los positivos. */
export function formatSignedRounded(amount: string): string {
  return Number(amount) > 0 ? `+${formatEurRounded(amount)}` : formatEurRounded(amount);
}

/** Los últimos `count` meses hasta el actual, del más reciente al más antiguo ("AAAA-MM"). */
export function recentMonths(count: number): string[] {
  const now = new Date();
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  });
}

/**
 * Texto que se propone para «¿Aplicar siempre?»: el concepto en mayúsculas y sin acentos (como
 * lo compara el backend), sin las palabras con números (fechas, referencias de tarjeta…).
 * El usuario lo puede corregir antes de crear la regla.
 */
export function suggestPattern(description: string): string {
  const text = description
    .normalize('NFKD')
    .replace(/\p{M}/gu, '')
    .toUpperCase()
    .split(/\s+/)
    .filter(Boolean);
  const words = text.filter((word) => !/\d/.test(word));
  return (words.length > 0 ? words : text).join(' ');
}

/**
 * Fecha y hora de un evento (ISO con zona) en hora local:
 * "hoy 18:42" · "ayer 09:05" · "28/10 18:42" · "28/10/2025 18:42" (si es de otro año).
 */
export function formatMoment(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const dayStart = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((dayStart(now) - dayStart(d)) / 86_400_000);
  if (days === 0) return `hoy ${time}`;
  if (days === 1) return `ayer ${time}`;
  const date = `${pad(d.getDate())}/${pad(d.getMonth() + 1)}`;
  return d.getFullYear() === now.getFullYear()
    ? `${date} ${time}`
    : `${date}/${d.getFullYear()} ${time}`;
}

/** Días enteros transcurridos desde una fecha ISO. */
export function daysSince(iso: string, now: Date = new Date()): number {
  return Math.floor((now.getTime() - new Date(iso).getTime()) / 86_400_000);
}

/**
 * Participaciones escritas a la española ("0,25", "1,5", "3") → texto con punto ("0.25").
 * También vale con punto ("0.25"). Hasta 8 decimales. Devuelve null si no es mayor que 0.
 */
export function parseEsShares(text: string): string | null {
  const clean = text.trim().replace(/\s/g, '');
  const match = /^(\d+)(?:[,.](\d{1,8}))?$/.exec(clean);
  if (!match) return null;
  const value = `${match[1]}.${match[2] ?? '0'}`;
  return Number(value) > 0 ? value : null;
}

/** "1.50000000" → "1,5" · "0.00000012" → "0,00000012": sin ceros de más y con coma. */
export function formatShares(shares: string): string {
  const [integer, fraction = ''] = shares.split('.');
  const trimmed = fraction.replace(/0+$/, '');
  return trimmed ? `${integer},${trimmed}` : integer;
}

/** "731.400024" y "EUR" → "731,40 €" · con otra divisa, en esa divisa ("9,37 US$"). */
export function formatPrice(price: string, currency: string): string {
  return new Intl.NumberFormat('es-ES', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
    useGrouping: 'always',
  }).format(Number(price));
}

/**
 * TER escrito en porcentaje ("0,07" o "0,07 %") → fracción con 5 decimales ("0.00070"),
 * que es como lo guarda el backend. Vacío → null; inválido → undefined.
 */
export function parseTerPercent(text: string): string | null | undefined {
  const clean = text.trim().replace(/\s|%/g, '');
  if (clean === '') return null;
  const match = /^(\d{1,2})(?:[,.](\d{1,3}))?$/.exec(clean);
  if (!match) return undefined;
  const thousandths = Number(match[1]) * 1000 + Number((match[2] ?? '').padEnd(3, '0'));
  // porcentaje con 3 decimales → fracción con 5: 0,070 % = 70 milésimas = 0.00070
  return `0.${String(thousandths).padStart(5, '0')}`;
}

/** "0.00070" → "0,07 %" (para enseñar o para rellenar el campo). */
export function formatTerPercent(ter: string): string {
  const percent = (Number(ter) * 100).toFixed(3).replace(/0$/, '');
  return `${percent.replace('.', ',')} %`;
}
