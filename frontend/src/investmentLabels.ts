// Textos de los tipos de producto y de operación (Inversiones, Fase 3)
import type { OperationKind, ProductKind } from './api';

export const PRODUCT_KINDS: { value: ProductKind; label: string }[] = [
  { value: 'etf', label: 'ETF' },
  { value: 'stock', label: 'Acción' },
  { value: 'fund', label: 'Fondo' },
  { value: 'crypto', label: 'Cripto' },
  { value: 'pension', label: 'Plan de pensiones' },
  { value: 'commodity', label: 'Materia prima (oro…)' },
  { value: 'other', label: 'Otro' },
];

export function kindLabel(kind: ProductKind): string {
  return PRODUCT_KINDS.find((k) => k.value === kind)?.label ?? kind;
}

export const OPERATION_KINDS: { value: OperationKind; label: string; amountHint: string }[] = [
  { value: 'buy', label: 'Compra', amountHint: 'Lo que salió de la cuenta, con comisiones' },
  { value: 'sell', label: 'Venta', amountHint: 'Lo que entró en la cuenta' },
  { value: 'dividend', label: 'Dividendo', amountHint: 'Lo que cobraste' },
  { value: 'fee', label: 'Comisión', amountHint: 'Lo que pagaste' },
];

export function operationLabel(kind: OperationKind): string {
  return OPERATION_KINDS.find((k) => k.value === kind)?.label ?? kind;
}
