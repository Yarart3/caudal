import { useRef, useState, type DragEvent } from 'react';
import { api, errorMessage, type Account, type InvestmentImportResult } from '../api';
import { notifyDataChanged } from '../events';
import { formatDate, formatEur, formatShares } from '../format';
import { operationLabel } from '../investmentLabels';

/** "1 operación" · "3 operaciones" (el plural pierde la tilde). */
function operations(count: number): string {
  return `${count} ${count === 1 ? 'operación' : 'operaciones'}`;
}

/**
 * «Importar historial» con la plantilla de Caudal (Fase 3, parte 3.3d2). Dos pasos: el archivo
 * se sube primero para la vista previa (no se guarda nada) y después se confirma; entra todo o
 * nada. El archivo solo vive en el navegador mientras dura: no se guarda en ningún sitio.
 */
export function InvestmentImportCard({
  accounts,
  hasProducts,
  onImported,
}: {
  accounts: Account[];
  hasProducts: boolean;
  onImported: (message: string) => void;
}) {
  const [accountId, setAccountId] = useState<number>(accounts[0]?.id ?? 0);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<InvestmentImportResult | null>(null);
  const [busy, setBusy] = useState<null | 'preview' | 'confirm'>(null);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  function reset() {
    setFile(null);
    setPreview(null);
    setError(null);
    if (fileInput.current) fileInput.current.value = '';
  }

  async function check(chosen: File) {
    setFile(chosen);
    setPreview(null);
    setError(null);
    setBusy('preview');
    try {
      setPreview(await api.importInvestments(accountId, chosen, false));
    } catch (err) {
      setError(errorMessage(err));
      setFile(null);
    } finally {
      setBusy(null);
      if (fileInput.current) fileInput.current.value = ''; // permite volver a elegir el mismo
    }
  }

  async function confirm() {
    if (!file) return;
    setBusy('confirm');
    setError(null);
    try {
      const result = await api.importInvestments(accountId, file, true);
      if (result.saved) {
        notifyDataChanged();
        reset();
        onImported(`${operations(result.new)} importada${result.new === 1 ? '' : 's'}`);
      } else {
        setPreview(result); // algo ha cambiado desde la vista previa: se enseñan los errores
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    setOver(false);
    const dropped = event.dataTransfer.files[0];
    if (dropped) void check(dropped);
  }

  const canConfirm = preview !== null && preview.errors.length === 0 && preview.new > 0;

  return (
    <section className="card panel">
      <div className="between">
        <h2>Importar historial</h2>
        <span className="row" style={{ gap: 12, fontSize: 14 }}>
          <a className="link-btn" href="/api/investments/template?format=xlsx" download>
            Plantilla Excel
          </a>
          <a className="link-btn" href="/api/investments/template?format=csv" download>
            Plantilla CSV
          </a>
        </span>
      </div>
      <p className="muted" style={{ fontSize: 13 }}>
        Para cargar de golpe tus compras antiguas. Rellena la hoja «Operaciones» de la plantilla
        (dentro tiene instrucciones y un ejemplo) y súbela aquí. Antes de guardar verás qué entra.
        {!hasProducts && ' Primero añade tus productos: la plantilla los busca por ISIN o símbolo.'}
      </p>

      <div className="field">
        <label htmlFor="imp-account">Cuenta</label>
        <select
          id="imp-account"
          value={accountId}
          onChange={(e) => {
            setAccountId(Number(e.target.value));
            reset();
          }}
          disabled={busy !== null}
        >
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </div>

      <label
        htmlFor="imp-file"
        className={`drop${over ? ' over' : ''}${busy ? ' busy' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={handleDrop}
      >
        <strong style={{ fontSize: 15 }}>
          {busy === 'preview'
            ? 'Revisando…'
            : file
              ? file.name
              : 'Arrastra aquí la plantilla rellena'}
        </strong>
        <span className="muted" style={{ fontSize: 13 }}>
          o haz clic para seleccionarla · .xlsx o .csv
        </span>
        <input
          id="imp-file"
          ref={fileInput}
          type="file"
          accept=".xlsx,.csv"
          className="sr-only"
          disabled={busy !== null}
          onChange={(e) => {
            const chosen = e.target.files?.[0];
            if (chosen) void check(chosen);
          }}
        />
      </label>

      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}

      {preview && (
        <div className="result" role="status">
          <strong>
            {preview.read} fila{preview.read === 1 ? '' : 's'} leída
            {preview.read === 1 ? '' : 's'} · {preview.new} nueva{preview.new === 1 ? '' : 's'} ·{' '}
            {preview.duplicates} ya estaba{preview.duplicates === 1 ? '' : 'n'}
            {preview.errors.length > 0 &&
              ` · ${preview.errors.length} con error${preview.errors.length === 1 ? '' : 'es'}`}
          </strong>
          {preview.errors.length > 0 && (
            <>
              <span>
                Corrige estas filas en el archivo y vuelve a subirlo (no se ha guardado nada):
              </span>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {preview.errors.slice(0, 20).map((e, i) => (
                  <li
                    key={`${e.row}-${i}`}
                    className="err"
                    style={{ background: 'none', padding: 0 }}
                  >
                    {e.message}
                  </li>
                ))}
              </ul>
              {preview.errors.length > 20 && (
                <span className="muted">… y {preview.errors.length - 20} más</span>
              )}
            </>
          )}
          {preview.errors.length === 0 && preview.new === 0 && (
            <span>Todas las filas ya estaban importadas: no hay nada nuevo.</span>
          )}
        </div>
      )}

      {preview && preview.operations.length > 0 && preview.errors.length === 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ minWidth: 640 }}>
            <thead>
              <tr>
                <th>Fila</th>
                <th>Fecha</th>
                <th>Producto</th>
                <th>Tipo</th>
                <th className="r">Participaciones</th>
                <th className="r">Importe</th>
              </tr>
            </thead>
            <tbody>
              {preview.operations.map((op) => (
                <tr key={op.row}>
                  <td className="muted">{op.row}</td>
                  <td className="tnum">{formatDate(op.date)}</td>
                  <td>{op.product_name}</td>
                  <td>{operationLabel(op.kind)}</td>
                  <td className="r tnum">
                    {Number(op.shares) > 0 ? formatShares(op.shares) : '—'}
                  </td>
                  <td className="r tnum">{formatEur(op.amount_eur)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {preview.new > preview.operations.length && (
            <p className="muted" style={{ fontSize: 13 }}>
              Se enseñan las {preview.operations.length} primeras de {preview.new}.
            </p>
          )}
        </div>
      )}

      {preview && (
        <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void confirm()}
            disabled={!canConfirm || busy !== null}
          >
            {busy === 'confirm' ? 'Importando…' : `Importar ${operations(preview.new)}`}
          </button>
          <button type="button" className="btn" onClick={reset} disabled={busy !== null}>
            Cancelar
          </button>
        </div>
      )}
    </section>
  );
}
