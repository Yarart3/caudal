// Resultado de «¿Aplicar siempre?» y el mensaje que se enseña después (va aparte del componente
// para que la recarga en caliente de Vite funcione: un .tsx solo exporta componentes).

export type ApplyAlwaysResult = { created: boolean; categorized: number; pattern: string };

/** «Regla «BON PREU» creada · 3 movimientos más categorizados» */
export function appliedMessage(result: ApplyAlwaysResult): string | null {
  if (!result.created) return null;
  const more =
    result.categorized === 0
      ? 'no había más pendientes con ese texto'
      : `${result.categorized} ${result.categorized === 1 ? 'movimiento más categorizado' : 'movimientos más categorizados'}`;
  return `Regla «${result.pattern}» creada · ${more}`;
}
