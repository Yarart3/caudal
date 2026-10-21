import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react';
import {
  api,
  errorMessage,
  type Account,
  type ImportResult,
  type RowError,
  type Transaction,
} from '../api';
import { AppShell } from '../AppShell';
import { formatDate, formatEur, parseEsAmount, todayIso } from '../format';

const BANKS = { imagin: 'imagin', wise: 'Wise' } as const;
type Bank = keyof typeof BANKS;

/** Fila del extracto que no se pudo leer y que el usuario quiere apuntar a mano. */
type Pending = { accountId: number; error: RowError; key: number };

/**
 * Pantalla Importar (Fase 1b): elegir cuenta, soltar el extracto, ver el resumen y apuntar a
 * mano las filas que no se han podido leer. En la 1c pasa a formar parte de Movimientos.
 */
export function ImportPage() {
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);

  useEffect(() => {
    api
      .accounts()
      .then(setAccounts)
      .catch((err: unknown) => setLoadError(errorMessage(err)));
  }, []);

  return (
    <AppShell title="Movimientos" current="Movimientos">
      {loadError && (
        <p className="err" role="alert">
          {loadError}
        </p>
      )}
      {accounts === null ? (
        !loadError && <p className="muted">Cargando…</p>
      ) : (
        <section className="r2e">
          <ImportCard
            accounts={accounts}
            onAccountCreated={(account) => setAccounts([...accounts, account])}
            onAddManually={(accountId, error) => setPending({ accountId, error, key: Date.now() })}
          />
          <ManualCard key={pending?.key ?? 0} accounts={accounts} pending={pending} />
        </section>
      )}
    </AppShell>
  );
}

// ---------- Importar extracto ----------

type LastImport = { accountId: number; accountName: string; fileName: string; data: ImportResult };

function ImportCard({
  accounts,
  onAccountCreated,
  onAddManually,
}: {
  accounts: Account[];
  onAccountCreated: (account: Account) => void;
  onAddManually: (accountId: number, error: RowError) => void;
}) {
  const importable = accounts.filter((a) => a.import_format !== null);
  const [accountId, setAccountId] = useState<number | null>(importable[0]?.id ?? null);
  const [creating, setCreating] = useState(false);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<LastImport | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const account = importable.find((a) => a.id === accountId) ?? null;

  async function upload(file: File) {
    if (!account || busy) return;
    if (!file.name.toLowerCase().endsWith('.xlsx')) {
      setError('El extracto tiene que ser un Excel (.xlsx), tal cual lo descargas del banco');
      return;
    }
    setBusy(true);
    setError(null);
    setLast(null);
    try {
      const data = await api.importStatement(account.id, file);
      setLast({ accountId: account.id, accountName: account.name, fileName: file.name, data });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = ''; // permite volver a elegir el mismo
    }
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    setOver(false);
    const file = event.dataTransfer.files[0];
    if (file) void upload(file);
  }

  if (importable.length === 0 || creating) {
    return (
      <div className="card panel">
        <h2>Importar extracto bancario</h2>
        <NewAccountForm
          first={importable.length === 0}
          onCancel={() => setCreating(false)}
          onCreated={(created) => {
            onAccountCreated(created);
            setAccountId(created.id);
            setCreating(false);
          }}
        />
      </div>
    );
  }

  return (
    <div className="card panel">
      <div className="between">
        <h2>Importar extracto bancario</h2>
        <button type="button" className="link-btn" onClick={() => setCreating(true)}>
          + Nueva cuenta
        </button>
      </div>
      <div className="field">
        <label htmlFor="cuenta">Cuenta</label>
        <select
          id="cuenta"
          value={accountId ?? ''}
          onChange={(e) => setAccountId(Number(e.target.value))}
          disabled={busy}
        >
          {importable.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({BANKS[a.import_format as Bank]})
            </option>
          ))}
        </select>
      </div>

      <label
        htmlFor="fichero"
        className={`drop${over ? ' over' : ''}${busy ? ' busy' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={handleDrop}
      >
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#5B616B"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M12 16V4" />
          <path d="M7 9l5-5 5 5" />
          <path d="M4 20h16" />
        </svg>
        <strong style={{ fontSize: 15 }}>
          {busy ? 'Importando…' : 'Arrastra aquí el extracto en Excel'}
        </strong>
        <span className="muted" style={{ fontSize: 13 }}>
          o haz clic para seleccionarlo · .xlsx, tal cual lo descargas del banco
        </span>
        <input
          id="fichero"
          ref={fileInput}
          type="file"
          accept=".xlsx"
          className="sr-only"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void upload(file);
          }}
        />
      </label>

      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      {last && (
        <ImportSummary
          last={last}
          onAddManually={(rowError) => onAddManually(last.accountId, rowError)}
        />
      )}
    </div>
  );
}

function ImportSummary({
  last,
  onAddManually,
}: {
  last: LastImport;
  onAddManually: (error: RowError) => void;
}) {
  const { data } = last;
  const newShare = data.read === 0 ? 0 : Math.round((data.new / data.read) * 100);
  const parts = [
    `${data.new} nuevos`,
    `${data.duplicates} ya existían`,
    `${data.categorized} ${data.categorized === 1 ? 'categorizado' : 'categorizados'} automáticamente`,
    `${data.review} por revisar`,
    `${data.internal} ${data.internal === 1 ? 'transferencia interna' : 'transferencias internas'}`,
  ];
  if (data.errors.length > 0) parts.push(`${data.errors.length} con error`);

  return (
    <>
      <div className="result" role="status">
        <strong>
          {last.accountName} · {data.read}{' '}
          {data.read === 1 ? 'movimiento leído' : 'movimientos leídos'}
        </strong>
        <div className="track" style={{ background: '#D5E6DF' }}>
          <div style={{ width: `${newShare}%`, background: 'var(--accent)' }} />
        </div>
        <span style={{ color: '#3F454D' }}>{parts.join(' · ')}</span>
        {data.closing_balance !== null && data.closing_date !== null && (
          <span className="muted" style={{ fontSize: 13 }}>
            Saldo según el extracto: {formatEur(data.closing_balance)} a{' '}
            {formatDate(data.closing_date)}
          </span>
        )}
      </div>

      {data.warnings.map((warning) => (
        <p key={warning} className="note">
          {warning}
        </p>
      ))}

      {data.errors.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <strong style={{ fontSize: 14 }}>Filas que no se han podido leer</strong>
          <span className="muted" style={{ fontSize: 13 }}>
            No se han importado. Mira esa fila en el extracto y apúntala a mano.
          </span>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ minWidth: 420 }}>
              <thead>
                <tr>
                  <th>Fila</th>
                  <th>Problema</th>
                  <th className="r">
                    <span className="sr-only">Acción</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.errors.map((rowError) => (
                  <tr key={`${rowError.row}-${rowError.field}`}>
                    <td className="tnum">{rowError.row}</td>
                    <td>{rowError.message}</td>
                    <td className="r">
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => onAddManually(rowError)}
                      >
                        Añadir a mano
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

function NewAccountForm({
  first,
  onCreated,
  onCancel,
}: {
  first: boolean;
  onCreated: (account: Account) => void;
  onCancel: () => void;
}) {
  const [bank, setBank] = useState<Bank>('imagin');
  const [name, setName] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSending(true);
    setError(null);
    try {
      const account = await api.createAccount({
        name: name.trim() || BANKS[bank],
        kind: 'spending',
        import_format: bank,
        // El saldo de Wise está en el fondo monetario: cuenta como liquidez (DISENO 5)
        liquidity_type: bank === 'wise' ? 'money_market' : 'cash',
      });
      onCreated(account);
    } catch (err) {
      setError(errorMessage(err));
      setSending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="panel-form" noValidate>
      <p className="muted" style={{ fontSize: 14 }}>
        {first
          ? 'Primero, crea la cuenta del banco del que vas a importar.'
          : 'Nueva cuenta de banco para importar sus extractos.'}
      </p>
      <div className="field">
        <label htmlFor="banco">Banco</label>
        <select id="banco" value={bank} onChange={(e) => setBank(e.target.value as Bank)}>
          {Object.entries(BANKS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="nombre">Nombre de la cuenta</label>
        <input
          id="nombre"
          type="text"
          maxLength={60}
          placeholder={BANKS[bank]}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      {error && (
        <span className="err" role="alert">
          {error}
        </span>
      )}
      <div className="row">
        <button type="submit" className="btn btn-primary" disabled={sending}>
          {sending ? 'Creando…' : 'Crear cuenta'}
        </button>
        {!first && (
          <button type="button" className="link-btn" onClick={onCancel}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}

// ---------- Añadir movimiento manual ----------

function ManualCard({ accounts, pending }: { accounts: Account[]; pending: Pending | null }) {
  const [kind, setKind] = useState<'expense' | 'income'>('expense');
  const [description, setDescription] = useState('');
  const [date, setDate] = useState(todayIso());
  const [amount, setAmount] = useState('');
  const [accountId, setAccountId] = useState<number | null>(
    pending?.accountId ?? accounts[0]?.id ?? null,
  );
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Transaction | null>(null);
  const first = useRef<HTMLInputElement>(null);

  // Si viene de "Añadir a mano", el foco va directo al formulario
  useEffect(() => {
    if (pending) first.current?.focus();
  }, [pending]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const value = parseEsAmount(amount);
    if (accountId === null) return setError('Elige la cuenta');
    if (description.trim() === '') return setError('Escribe el concepto');
    if (date === '') return setError('Elige la fecha');
    if (value === null) return setError('Escribe un importe mayor que 0 (ej. 12,50)');

    setSending(true);
    setError(null);
    try {
      const created = await api.createTransaction({
        account_id: accountId,
        date,
        description: description.trim(),
        amount: kind === 'expense' ? `-${value}` : value,
      });
      setSaved(created);
      setDescription('');
      setAmount('');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  }

  if (accounts.length === 0) {
    return (
      <div className="card panel">
        <h2>Añadir movimiento manual</h2>
        <p className="muted">Primero crea una cuenta.</p>
      </div>
    );
  }

  return (
    <form className="card panel" onSubmit={handleSubmit} noValidate>
      <h2>Añadir movimiento manual</h2>
      {pending && (
        <p className="note">
          {pending.error.message}. Busca esa fila en el Excel y copia aquí su concepto, fecha e
          importe.
        </p>
      )}
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
          <label htmlFor="concepto">Concepto</label>
          <input
            id="concepto"
            ref={first}
            type="text"
            maxLength={200}
            placeholder="Ej. Cena con amigos"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="fecha">Fecha</label>
          <input id="fecha" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="importe">Importe (€)</label>
          <input
            id="importe"
            type="text"
            inputMode="decimal"
            placeholder="0,00"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </div>
        <div className="field span2">
          <label htmlFor="cuenta-m">Cuenta</label>
          <select
            id="cuenta-m"
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
      </div>
      {error && (
        <span className="err" role="alert">
          {error}
        </span>
      )}
      {saved && !error && (
        <p className="result" role="status">
          Guardado: {saved.description} · {formatEur(saved.amount)} · {formatDate(saved.date)}
          {saved.is_internal_transfer
            ? ' · marcado como transferencia interna'
            : saved.category_status === 'auto'
              ? ' · categorizado automáticamente'
              : ' · queda por revisar hasta que le pongas categoría'}
        </p>
      )}
      <button type="submit" className="btn btn-primary" disabled={sending}>
        {sending ? 'Guardando…' : 'Guardar movimiento'}
      </button>
    </form>
  );
}
