import { useState, type FormEvent } from 'react';
import {
  api,
  errorMessage,
  type Account,
  type Operation,
  type OperationCreate,
  type OperationKind,
  type Product,
} from '../api';
import { notifyDataChanged } from '../events';
import { formatShares, parseEsAmount, parseEsShares, toEsAmount, todayIso } from '../format';
import { OPERATION_KINDS, operationLabel } from '../investmentLabels';
import { Modal } from './Modal';

export type OperationMode = { kind: 'new' } | { kind: 'edit' | 'duplicate'; op: Operation };

/**
 * «+ Añadir compra / venta», editar y duplicar. Duplicar copia todo menos la fecha (hoy):
 * sirve para repetir una compra habitual cambiando solo la fecha y las cifras.
 */
export function OperationDialog({
  mode,
  accounts,
  products,
  onClose,
  onFinished,
}: {
  mode: OperationMode;
  accounts: Account[];
  products: Product[];
  onClose: () => void;
  onFinished: (message: string) => void;
}) {
  const source = mode.kind === 'new' ? null : mode.op;
  const editing = mode.kind === 'edit';
  const [kind, setKind] = useState<OperationKind>(source?.kind ?? 'buy');
  const [date, setDate] = useState(editing && source ? source.date : todayIso());
  const [accountId, setAccountId] = useState<number | null>(
    source?.account_id ?? accounts[0]?.id ?? null,
  );
  const [productId, setProductId] = useState<number | null>(
    source?.product_id ?? products[0]?.id ?? null,
  );
  const [shares, setShares] = useState(
    source && Number(source.shares) > 0 ? formatShares(source.shares) : '',
  );
  const [amount, setAmount] = useState(source ? toEsAmount(source.amount_eur) : '');
  const [fee, setFee] = useState(source?.fee_eur ? toEsAmount(source.fee_eur) : '');
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const withShares = kind === 'buy' || kind === 'sell';
  const hint = OPERATION_KINDS.find((k) => k.value === kind)?.amountHint ?? '';
  const title = editing
    ? 'Editar operación'
    : mode.kind === 'duplicate'
      ? 'Duplicar operación'
      : 'Añadir compra / venta';

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const amountValue = parseEsAmount(amount);
    const sharesValue = withShares ? parseEsShares(shares) : '0';
    const feeValue = fee.trim() === '' ? null : (parseEsAmount(fee) ?? undefined);
    if (accountId === null) return setError('Elige la cuenta');
    if (productId === null) return setError('Elige el producto');
    if (date === '') return setError('Elige la fecha');
    if (sharesValue === null) return setError('Escribe las participaciones (ej. 0,25)');
    if (amountValue === null) return setError('Escribe el importe en euros (ej. 150,00)');
    if (feeValue === undefined) return setError('La comisión es un importe en euros (ej. 1,00)');
    const body: OperationCreate = {
      account_id: accountId,
      product_id: productId,
      date,
      kind,
      shares: sharesValue,
      amount_eur: amountValue,
      fee_eur: withShares ? feeValue : null,
    };
    setBusy(true);
    setError(null);
    try {
      if (editing && source) await api.updateOperation(source.id, body);
      else await api.createOperation(body);
      notifyDataChanged();
      onFinished(editing ? 'Operación guardada' : 'Operación añadida');
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!source) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteOperation(source.id);
      notifyDataChanged();
      onFinished('Operación borrada');
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
      setConfirmDelete(false);
    }
  }

  const errorBox = error && (
    <span className="err" role="alert">
      {error}
    </span>
  );

  if (confirmDelete && source) {
    return (
      <Modal title="¿Borrar esta operación?" onClose={onClose}>
        <p>
          <strong>
            {operationLabel(source.kind)} · {source.product_name}
          </strong>
        </p>
        <p className="note">No se puede deshacer.</p>
        {errorBox}
        <div className="row" style={{ flexWrap: 'wrap' }}>
          <button type="button" className="btn btn-danger" onClick={handleDelete} disabled={busy}>
            {busy ? 'Borrando…' : 'Sí, borrar'}
          </button>
          <button type="button" className="btn" onClick={() => setConfirmDelete(false)}>
            Cancelar
          </button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form className="panel-form" onSubmit={handleSubmit} noValidate>
        <div
          className="row"
          role="group"
          aria-label="Tipo de operación"
          style={{ gap: 8, flexWrap: 'wrap' }}
        >
          {OPERATION_KINDS.map((k) => (
            <button
              key={k.value}
              type="button"
              className={`toggle${kind === k.value ? (k.value === 'sell' || k.value === 'fee' ? ' on-g' : ' on-i') : ''}`}
              aria-pressed={kind === k.value}
              onClick={() => setKind(k.value)}
            >
              {k.label}
            </button>
          ))}
        </div>
        <div className="grid2">
          <div className="field span2">
            <label htmlFor="op-product">Producto</label>
            <select
              id="op-product"
              value={productId ?? ''}
              onChange={(e) => setProductId(Number(e.target.value))}
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.isin ? ` · ${p.isin}` : ''}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="op-account">Cuenta</label>
            <select
              id="op-account"
              value={accountId ?? ''}
              onChange={(e) => setAccountId(Number(e.target.value))}
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="op-date">Fecha</label>
            <input
              id="op-date"
              type="date"
              max={todayIso()}
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          {withShares && (
            <div className="field">
              <label htmlFor="op-shares">Participaciones</label>
              <input
                id="op-shares"
                type="text"
                inputMode="decimal"
                placeholder="0,25"
                value={shares}
                onChange={(e) => setShares(e.target.value)}
              />
            </div>
          )}
          <div className="field">
            <label htmlFor="op-amount">Importe total (€)</label>
            <input
              id="op-amount"
              type="text"
              inputMode="decimal"
              placeholder="0,00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
            <span className="muted" style={{ fontSize: 12 }}>
              {hint}
            </span>
          </div>
          {withShares && (
            <div className="field">
              <label htmlFor="op-fee">Comisión (€, opcional)</label>
              <input
                id="op-fee"
                type="text"
                inputMode="decimal"
                placeholder="1,00"
                value={fee}
                onChange={(e) => setFee(e.target.value)}
              />
              <span className="muted" style={{ fontSize: 12 }}>
                La parte del importe que fue comisión
              </span>
            </div>
          )}
        </div>
        {errorBox}
        <div className="between">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? 'Guardando…' : editing ? 'Guardar cambios' : 'Añadir operación'}
          </button>
          {editing && (
            <button type="button" className="link-btn" onClick={() => setConfirmDelete(true)}>
              Borrar operación
            </button>
          )}
        </div>
      </form>
    </Modal>
  );
}
