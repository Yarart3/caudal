import { useState, type FormEvent } from 'react';
import {
  api,
  errorMessage,
  type Listing,
  type PricePreview,
  type Product,
  type ProductKind,
} from '../api';
import { notifyDataChanged } from '../events';
import { formatDate, formatPrice, formatTerPercent, parseTerPercent } from '../format';
import { PRODUCT_KINDS } from '../investmentLabels';
import { Modal } from './Modal';

const ISIN = /^[A-Z]{2}[A-Z0-9]{9}\d$/;

/**
 * Alta y edición de un producto. Alta con precio de Yahoo: buscar (ISIN, ticker o nombre),
 * elegir o escribir el símbolo, «Comprobar precio» y guardar. El backend vuelve a comprobar
 * el precio al guardar. `product` null → alta nueva.
 */
export function ProductDialog({
  product,
  onClose,
  onFinished,
}: {
  product: Product | null;
  onClose: () => void;
  onFinished: (message: string) => void;
}) {
  const editing = product !== null;
  const [manual, setManual] = useState(product?.price_source === 'manual');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Listing[] | null>(null);
  const [symbol, setSymbol] = useState(product?.source_id ?? '');
  const [preview, setPreview] = useState<PricePreview | null>(null);
  const [name, setName] = useState(product?.name ?? '');
  const [isin, setIsin] = useState(product?.isin ?? '');
  const [kind, setKind] = useState<ProductKind>(product?.kind ?? 'etf');
  const [ter, setTer] = useState(product?.ter ? formatTerPercent(product.ter) : '');
  const [longTerm, setLongTerm] = useState(product?.long_term ?? true);
  const [busy, setBusy] = useState<null | 'search' | 'preview' | 'save' | 'delete'>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search() {
    const text = query.trim();
    if (text.length < 2) return setError('Escribe al menos 2 letras');
    setBusy('search');
    setError(null);
    try {
      setResults(await api.searchProducts(text));
      if (ISIN.test(text.toUpperCase()) && isin === '') setIsin(text.toUpperCase());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function check(value: string = symbol) {
    const text = value.trim().toUpperCase();
    if (text === '') return setError('Escribe el símbolo de Yahoo (por ejemplo, SXR8.DE)');
    setSymbol(text);
    setBusy('preview');
    setError(null);
    setPreview(null);
    try {
      const found = await api.previewProduct(text);
      setPreview(found);
      if (name.trim() === '' && found.name) setName(found.name);
      if (found.kind) setKind(found.kind);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const terValue = parseTerPercent(ter);
    const isinValue = isin.trim().toUpperCase() || null;
    if (name.trim() === '') return setError('Escribe el nombre del producto');
    if (terValue === undefined) return setError('El TER va en porcentaje, por ejemplo 0,07');
    if (isinValue && !ISIN.test(isinValue)) {
      return setError('El ISIN son 12 caracteres, como IE00B5BMR087 (o déjalo vacío)');
    }
    if (!editing && !manual && preview === null) {
      return setError('Comprueba antes el precio del símbolo');
    }
    setBusy('save');
    setError(null);
    try {
      if (product) {
        await api.updateProduct(product.id, {
          name: name.trim(),
          isin: isinValue,
          kind,
          ter: terValue,
          long_term: longTerm,
        });
        notifyDataChanged();
        onFinished('Producto guardado');
        return;
      }
      await api.createProduct({
        name: name.trim(),
        isin: isinValue,
        ticker: null,
        kind,
        price_source: manual ? 'manual' : 'yahoo',
        source_id: manual ? null : symbol.trim().toUpperCase(),
        ter: terValue,
        long_term: longTerm,
      });
      notifyDataChanged();
      onFinished(
        manual
          ? 'Producto guardado'
          : 'Producto guardado. Su histórico de precios se descargará en la próxima actualización.',
      );
    } catch (err) {
      setError(errorMessage(err));
      setBusy(null);
    }
  }

  async function handleDelete() {
    if (!product) return;
    setBusy('delete');
    setError(null);
    try {
      await api.deleteProduct(product.id);
      notifyDataChanged();
      onFinished('Producto borrado');
    } catch (err) {
      setError(errorMessage(err));
      setBusy(null);
      setConfirmDelete(false);
    }
  }

  const errorBox = error && (
    <span className="err" role="alert">
      {error}
    </span>
  );

  if (confirmDelete && product) {
    return (
      <Modal title="¿Borrar este producto?" onClose={onClose}>
        <p>
          <strong>{product.name}</strong>
        </p>
        <p className="note">
          Se borran también sus precios guardados. Si tiene operaciones, primero hay que borrarlas.
        </p>
        {errorBox}
        <div className="row" style={{ flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-danger"
            onClick={handleDelete}
            disabled={busy !== null}
          >
            {busy === 'delete' ? 'Borrando…' : 'Sí, borrar'}
          </button>
          <button type="button" className="btn" onClick={() => setConfirmDelete(false)}>
            Cancelar
          </button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title={editing ? 'Editar producto' : 'Añadir producto'} onClose={onClose}>
      <form className="panel-form" onSubmit={handleSubmit} noValidate>
        {!editing && (
          <label className="check">
            <input
              type="checkbox"
              checked={manual}
              onChange={(e) => {
                setManual(e.target.checked);
                setError(null);
              }}
            />
            Sin precio en internet (plan de pensiones, depósito…): anotaré su valor a mano
          </label>
        )}

        {!editing && !manual && (
          <>
            <div className="field">
              <label htmlFor="prod-search">Buscar por ISIN, ticker o nombre</label>
              <div className="row" style={{ gap: 8 }}>
                <input
                  id="prod-search"
                  type="search"
                  placeholder="IE00B5BMR087"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      void search();
                    }
                  }}
                />
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => void search()}
                  disabled={busy !== null}
                >
                  {busy === 'search' ? 'Buscando…' : 'Buscar'}
                </button>
              </div>
            </div>
            {results !== null &&
              (results.length === 0 ? (
                <p className="muted" style={{ fontSize: 13 }}>
                  Yahoo no devuelve nada para eso. Si conoces el símbolo, escríbelo abajo.
                </p>
              ) : (
                <ul className="pick-list" aria-label="Resultados de Yahoo">
                  {results.map((item) => (
                    <li key={item.symbol}>
                      <button type="button" onClick={() => void check(item.symbol)}>
                        <strong>{item.symbol}</strong>
                        <span className="muted">{item.name ?? ''}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              ))}
            <div className="field">
              <label htmlFor="prod-symbol">Símbolo de Yahoo</label>
              <div className="row" style={{ gap: 8 }}>
                <input
                  id="prod-symbol"
                  type="text"
                  placeholder="SXR8.DE"
                  value={symbol}
                  onChange={(e) => {
                    setSymbol(e.target.value);
                    setPreview(null);
                  }}
                />
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => void check()}
                  disabled={busy !== null}
                >
                  {busy === 'preview' ? 'Comprobando…' : 'Comprobar precio'}
                </button>
              </div>
              <span className="muted" style={{ fontSize: 12 }}>
                Yahoo suele devolver la cotización de Londres o Milán. Para Xetra, en euros, el
                símbolo acaba en .DE (por ejemplo, SXR8.DE).
              </span>
            </div>
            {preview && (
              <div className="result" role="status">
                <strong>
                  {formatPrice(preview.price, preview.currency)} · {formatDate(preview.price_date)}
                </strong>
                <span>
                  {preview.name ?? preview.symbol} · {preview.exchange ?? 'plaza desconocida'} ·{' '}
                  {preview.currency}
                </span>
                {preview.currency !== 'EUR' && (
                  <span className="note">
                    Este símbolo cotiza en {preview.currency}: el valor se pasará a euros. Si
                    compras en euros, busca su versión en Xetra (.DE).
                  </span>
                )}
              </div>
            )}
          </>
        )}

        {editing && product?.source_id && (
          <p className="muted" style={{ fontSize: 13 }}>
            Símbolo: <strong>{product.source_id}</strong> · {product.currency}. Para cambiarlo,
            borra el producto (si no tiene operaciones) y créalo otra vez.
          </p>
        )}

        <div className="grid2">
          <div className="field span2">
            <label htmlFor="prod-name">Nombre</label>
            <input
              id="prod-name"
              type="text"
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="prod-isin">ISIN (opcional)</label>
            <input
              id="prod-isin"
              type="text"
              maxLength={12}
              value={isin}
              onChange={(e) => setIsin(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="prod-kind">Tipo</label>
            <select
              id="prod-kind"
              value={kind}
              onChange={(e) => setKind(e.target.value as ProductKind)}
            >
              {PRODUCT_KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="prod-ter">TER, comisión anual (opcional)</label>
            <input
              id="prod-ter"
              type="text"
              inputMode="decimal"
              placeholder="0,07 %"
              value={ter}
              onChange={(e) => setTer(e.target.value)}
            />
          </div>
          <label className="check" style={{ alignSelf: 'end' }}>
            <input
              type="checkbox"
              checked={longTerm}
              onChange={(e) => setLongTerm(e.target.checked)}
            />
            A largo plazo
          </label>
        </div>
        {errorBox}
        <div className="between">
          <button type="submit" className="btn btn-primary" disabled={busy !== null}>
            {busy === 'save' ? 'Guardando…' : editing ? 'Guardar cambios' : 'Añadir producto'}
          </button>
          {editing && (
            <button type="button" className="link-btn" onClick={() => setConfirmDelete(true)}>
              Borrar producto
            </button>
          )}
        </div>
      </form>
    </Modal>
  );
}
