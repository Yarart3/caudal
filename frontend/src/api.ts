// Cliente de la API de Caudal. Todas las llamadas pasan por aquí.
// - La cookie de sesión la envía el navegador solo (misma web: credentials "same-origin").
// - Los errores llegan como ApiError con el mensaje en castellano que da el backend.

export type UserCard = {
  username: string;
  display_name: string;
  initial: string;
  color: string;
};

export type Me = UserCard & { is_admin: boolean };

// Dinero: viaja como texto ("-14.50") para no perder céntimos con los float de JavaScript
export type Account = {
  id: number;
  name: string;
  kind: 'spending' | 'investment' | 'mixed';
  import_format: 'imagin' | 'wise' | null;
  liquidity_type: 'cash' | 'money_market';
  reference_balance: string | null;
  reference_balance_date: string | null;
};

export type AccountCreate = {
  name: string;
  kind: Account['kind'];
  import_format: Account['import_format'];
  liquidity_type: Account['liquidity_type'];
};

export type RowError = { row: number; field: string; value: string; message: string };

export type ImportResult = {
  read: number;
  new: number;
  duplicates: number;
  review: number;
  internal: number;
  errors: RowError[];
  warnings: string[];
  closing_balance: string | null;
  closing_date: string | null;
};

export type Transaction = {
  id: number;
  account_id: number;
  date: string;
  description: string;
  amount: string;
  category_id: number | null;
  category_status: 'auto' | 'manual' | 'review';
  is_internal_transfer: boolean;
};

export type TransactionCreate = {
  account_id: number;
  date: string;
  description: string;
  amount: string;
};

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

type RequestOptions = { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; body?: unknown };

// Aviso de "la sesión ya no vale" (401). Lo registra AuthProvider para volver a "¿Quién entra?".
// El login no cuenta: ahí un 401 es "contraseña incorrecta".
let onSessionExpired: (() => void) | null = null;

export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler;
}

async function request<T>(path: string, { method = 'GET', body }: RequestOptions = {}): Promise<T> {
  // Un FormData (subida de archivos) va tal cual: el navegador pone el Content-Type multipart
  const isForm = body instanceof FormData;
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: body === undefined || isForm ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'No se puede conectar con Caudal. ¿Está arrancado?');
  }

  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const detail =
      data !== null &&
      typeof data === 'object' &&
      'detail' in data &&
      typeof data.detail === 'string'
        ? data.detail
        : `Error inesperado (${res.status})`;
    if (res.status === 401 && path !== '/api/auth/login') onSessionExpired?.();
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

/** Mensaje para mostrar al usuario a partir de cualquier error. */
export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Ha ocurrido un error inesperado';
}

export const api = {
  setupStatus: () => request<{ needs_setup: boolean }>('/api/setup/status'),
  setup: (gerardPassword: string, padresPassword: string) =>
    request<unknown>('/api/setup', {
      method: 'POST',
      body: { gerard_password: gerardPassword, padres_password: padresPassword },
    }),
  users: () => request<UserCard[]>('/api/auth/users'),
  login: (username: string, password: string) =>
    request<Me>('/api/auth/login', { method: 'POST', body: { username, password } }),
  logout: () => request<void>('/api/auth/logout', { method: 'POST' }),
  me: () => request<Me>('/api/auth/me'),
  accounts: () => request<Account[]>('/api/accounts'),
  createAccount: (account: AccountCreate) =>
    request<Account>('/api/accounts', { method: 'POST', body: account }),
  importStatement: (accountId: number, file: File) => {
    const form = new FormData();
    form.append('account_id', String(accountId));
    form.append('file', file);
    return request<ImportResult>('/api/imports', { method: 'POST', body: form });
  },
  createTransaction: (tx: TransactionCreate) =>
    request<Transaction>('/api/transactions', { method: 'POST', body: tx }),
};
