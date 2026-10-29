import { useState, type FormEvent } from 'react';
import {
  api,
  errorMessage,
  type Account,
  type Category,
  type Transaction,
  type TransactionUpdate,
} from '../api';
import { notifyDataChanged } from '../events';
import { parseEsAmount, toEsAmount, todayIso } from '../format';
import { ApplyAlways } from './ApplyAlways';
import { appliedMessage } from './applyAlwaysResult';
import { CategorySelect } from './CategorySelect';
import { Modal } from './Modal';

type Step = 'form' | 'confirm-delete' | { applyFor: Transaction; categoryId: number };

/**
 * Alta y edición de un movimiento (y borrado). Si se le pone una categoría a mano, después
 * ofrece «¿Aplicar siempre?».
 * - `tx` null → alta nueva.
 * - `onFinished(message)` se llama al terminar, con un texto para enseñar si hace falta.
 */
export function TransactionDialog({
  tx,
  accounts,
  categories,
  onClose,
  onFinished,
}: {
  tx: Transaction | null;
  accounts: Account[];
  categories: Category[];
  onClose: () => void;
  onFinished: (message: string | null) => void;
}) {
  const [kind, setKind] = useState<'expense' | 'income'>(
    tx && Number(tx.amount) > 0 ? 'income' : 'expense',
  );
  const [description, setDescription] = useState(tx?.description ?? '');
  const [date, setDate] = useState(tx?.date ?? todayIso());
  const [amount, setAmount] = useState(tx ? toEsAmount(tx.amount) : '');
  const [accountId, setAccountId] = useState<number | null>(
    tx?.account_id ?? accounts[0]?.id ?? null,
  );
  const [categoryId, setCategoryId] = useState<number | null>(tx?.category_id ?? null);
  const [internal, setInternal] = useState(tx?.is_internal_transfer ?? false);
  const [step, setStep] = useState<Step>('form');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const title = tx ? 'Editar movimiento' : 'Añadir movimiento';
  const categoryName = (id: number) => categories.find((c) => c.id === id)?.name ?? '';

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const value = parseEsAmount(amount);
    if (accountId === null) return setError('Elige la cuenta');
    if (description.trim() === '') return setError('Escribe el concepto');
    if (date === '') return setError('Elige la fecha');
    if (value === null) return setError('Escribe un importe mayor que 0 (ej. 12,50)');
    const signed = kind === 'expense' ? `-${value}` : value;

    setBusy(true);
    setError(null);
    try {
      let saved: Transaction;
      if (tx === null) {
        saved = await api.createTransaction({
          account_id: accountId,
          date,
          description: description.trim(),
          amount: signed,
        });
      } else {
        const changes: TransactionUpdate = {};
        if (accountId !== tx.account_id) changes.account_id = accountId;
        if (date !== tx.date) changes.date = date;
        if (description.trim() !== tx.description) changes.description = description.trim();
        if (Number(signed) !== Number(tx.amount)) changes.amount = signed;
        saved = Object.keys(changes).length ? await api.updateTransaction(tx.id, changes) : tx;
      }

      // Marca de transferencia y categoría, después del resto (el alta no las admite)
      if (internal !== saved.is_internal_transfer) {
        saved = await api.updateTransaction(saved.id, { is_internal_transfer: internal });
      }
      // Se manda si ha cambiado, o si la que se eligió no es la que han puesto las reglas
      const setByHand =
        categoryId !== (tx?.category_id ?? null) ||
        (categoryId !== null && categoryId !== saved.category_id);
      if (setByHand && !internal) {
        saved = await api.updateTransaction(saved.id, { category_id: categoryId });
      }
      notifyDataChanged();

      if (setByHand && categoryId !== null && !saved.is_internal_transfer) {
        setStep({ applyFor: saved, categoryId });
        setBusy(false);
      } else {
        onFinished(tx ? 'Movimiento guardado' : 'Movimiento añadido');
      }
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!tx) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteTransaction(tx.id);
      notifyDataChanged();
      onFinished('Movimiento borrado');
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  if (typeof step === 'object') {
    return (
      <Modal title="Movimiento guardado" onClose={() => onFinished('Movimiento guardado')}>
        <ApplyAlways
          description={step.applyFor.description}
          categoryId={step.categoryId}
          categoryName={categoryName(step.categoryId)}
          onDone={(result) => onFinished(appliedMessage(result) ?? 'Movimiento guardado')}
        />
      </Modal>
    );
  }

  if (step === 'confirm-delete' && tx) {
    return (
      <Modal title="¿Borrar este movimiento?" onClose={onClose}>
        <p>
          <strong>{tx.description}</strong>
        </p>
        <p className="note">
          No se puede deshacer. Si es de un extracto importado y vuelves a importar ese mismo
          extracto, volverá a aparecer.
        </p>
        {error && (
          <span className="err" role="alert">
            {error}
          </span>
        )}
        <div className="row" style={{ flexWrap: 'wrap' }}>
          <button type="button" className="btn btn-danger" onClick={handleDelete} disabled={busy}>
            {busy ? 'Borrando…' : 'Sí, borrar'}
          </button>
          <button type="button" className="btn" onClick={() => setStep('form')} disabled={busy}>
            Cancelar
          </button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form className="panel-form" onSubmit={handleSubmit} noValidate>
        <div className="row" role="group" aria-label="Tipo de movimiento" style={{ gap: 8 }}>
          <button
            type="button"
            className={`toggle${kind === 'expense' ? ' on-g' : ''}`}
            aria-pressed={kind === 'expense'}
            onClick={() => setKind('expense')}
          >
            Gasto
          </button>
          <button
            type="button"
            className={`toggle${kind === 'income' ? ' on-i' : ''}`}
            aria-pressed={kind === 'income'}
            onClick={() => setKind('income')}
          >
            Ingreso
          </button>
        </div>
        <div className="grid2">
          <div className="field span2">
            <label htmlFor="tx-concepto">Concepto</label>
            <input
              id="tx-concepto"
              type="text"
              maxLength={200}
              placeholder="Ej. Cena con amigos"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="tx-fecha">Fecha</label>
            <input
              id="tx-fecha"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="tx-importe">Importe (€)</label>
            <input
              id="tx-importe"
              type="text"
              inputMode="decimal"
              placeholder="0,00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="tx-cuenta">Cuenta</label>
            <select
              id="tx-cuenta"
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
            <label htmlFor="tx-categoria">Categoría</label>
            <CategorySelect
              id="tx-categoria"
              categories={categories}
              value={categoryId}
              onChange={setCategoryId}
              emptyLabel={tx ? 'Sin categoría (por revisar)' : 'Automática (según las reglas)'}
              disabled={internal}
            />
          </div>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={internal}
            onChange={(e) => setInternal(e.target.checked)}
          />
          Transferencia entre mis cuentas (no cuenta como gasto ni ingreso)
        </label>
        {error && (
          <span className="err" role="alert">
            {error}
          </span>
        )}
        <div className="between">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? 'Guardando…' : tx ? 'Guardar cambios' : 'Añadir movimiento'}
          </button>
          {tx && (
            <button
              type="button"
              className="link-btn danger"
              onClick={() => setStep('confirm-delete')}
              disabled={busy}
            >
              Borrar movimiento
            </button>
          )}
        </div>
      </form>
    </Modal>
  );
}
