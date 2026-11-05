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
  categorized: number;
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

export type StatusFilter = 'review' | 'auto' | 'manual' | 'internal';

export type TransactionFilters = {
  month?: string; // "AAAA-MM"
  q?: string;
  category?: number;
  status?: StatusFilter;
  account?: number;
  limit?: number;
  offset?: number;
};

export type TransactionPage = { items: Transaction[]; total: number };

export type TransactionUpdate = Partial<{
  account_id: number;
  date: string;
  description: string;
  amount: string;
  category_id: number | null; // null = sin categoría (por revisar)
  is_internal_transfer: boolean;
}>;

export type CategoryKind = 'expense' | 'income';

export type Category = {
  id: number;
  name: string;
  kind: CategoryKind;
  color: string;
  transactions: number;
  rules: number;
};

export type CategoryCreate = { name: string; kind: CategoryKind; color: string };

export type Rule = {
  id: number;
  pattern: string;
  category_id: number | null; // null = dejar por revisar
  priority: number;
  created_by: 'system' | 'user';
};

export type RuleSaved = { rule: Rule; replaced: boolean; categorized: number };

export type RulesApplied = { categorized: number; review: number };

export type TransactionCreate = {
  account_id: number;
  date: string;
  description: string;
  amount: string;
};

// Backups (Fase 1d). Son de la BD entera: todos los usuarios ven el mismo estado.
export type BackupDestination = {
  destination: 'usb' | 'onedrive';
  label: string; // "Pendrive" / "OneDrive"
  available: boolean; // el pendrive está conectado / la carpeta de OneDrive existe
  ok: boolean; // disponible y su último backup salió bien → ✓
  last_at: string | null;
  last_ok_at: string | null;
  message: string | null;
};

export type BackupStatus = {
  configured: boolean; // hay BACKUP_PASSWORD en el .env
  auto: boolean;
  last_backup_at: string | null;
  stale: boolean; // sin backups o el último tiene más de max_age_days días
  max_age_days: number;
  destinations: BackupDestination[];
};

export type BackupRun = { ok: boolean; filename: string; status: BackupStatus };

// Paneles (Fase 1c, parte 1.5). `month` = "AAAA-MM"; sin él, el mes del último movimiento.
export type AccountBalance = {
  id: number;
  name: string;
  kind: Account['kind'];
  liquidity_type: Account['liquidity_type'];
  balance: string;
};

export type NetWorthMonth = { month: string; liquidity: string; investments: string };

export type NetWorth = {
  month: string;
  net_worth: string;
  liquidity: string;
  investments: string; // Fase 3: de momento siempre 0
  savings: string; // ingresos − gastos del mes
  accounts: AccountBalance[];
  by_type: Record<Account['liquidity_type'], string>;
  history: NetWorthMonth[]; // 12 meses, del más antiguo al elegido
};

export type CashflowMonth = { month: string; income: string; expense: string };

export type CategorySpend = {
  category_id: number | null; // null = sin categoría
  name: string;
  color: string;
  amount: string;
};

export type Cashflow = {
  month: string;
  cash_total: string;
  income: string;
  expense: string; // en positivo
  savings: string;
  savings_rate: number | null; // % entero; null si no hay ingresos
  previous_expense: string;
  expense_change: number | null; // % frente al mes anterior; null si el anterior no tiene gastos
  history: CashflowMonth[];
  by_category: CategorySpend[];
};

export type BudgetStatus = 'ok' | 'near' | 'over';

export type BudgetLine = {
  category_id: number;
  name: string;
  color: string;
  budget: string | null; // null = sin presupuesto
  spent: string;
  remaining: string | null;
  percent: number | null;
  status: BudgetStatus | null;
};

export type Budgets = {
  month: string;
  total_budget: string;
  total_spent: string;
  lines: BudgetLine[]; // todas las categorías de gasto; las que tienen presupuesto, primero
};

/** amount null = quitar el presupuesto de esa categoría. */
export type BudgetChange = { category_id: number; amount: string | null };

export type AlertLevel = 'danger' | 'warning' | 'positive' | 'info';

export type Alert = {
  kind: 'budget_over' | 'spending_high' | 'expense_change' | 'recurring_new' | 'recurring_total';
  level: AlertLevel;
  title: string;
  message: string;
  category_id: number | null;
  amount: string | null;
};

export type Alerts = { month: string; items: Alert[] };

export type RecurringPayment = {
  key: string;
  description: string;
  frequency: 'monthly' | 'annual';
  amount: string;
  monthly_amount: string;
  occurrences: number;
  first_date: string;
  last_date: string;
  next_date: string;
  detected_on: string;
  is_new: boolean;
  category_id: number | null;
  category_name: string;
  category_color: string;
  account_name: string;
};

export type RecurringSummary = {
  month: string;
  monthly_total: string;
  items: RecurringPayment[];
};

export type Milestone = { amount: string; reached: boolean };

export type Goal = {
  month: string;
  net_worth: string;
  name: string | null; // null = sin objetivo
  target_amount: string | null;
  percent: number | null;
  remaining: string | null;
  last_milestone: string | null;
  next_milestones: string[];
  milestones: Milestone[];
};

// --- Inversiones (Fase 3) ---

export type ProductKind = 'etf' | 'stock' | 'fund' | 'crypto' | 'pension' | 'commodity' | 'other';

export type Product = {
  id: number;
  name: string;
  isin: string | null;
  ticker: string | null;
  kind: ProductKind;
  currency: string;
  price_source: 'yahoo' | 'manual' | 'morningstar' | 'coingecko';
  source_id: string | null;
  ter: string | null; // fracción: "0.00070" = 0,07 %
  long_term: boolean;
};

export type ProductCreate = {
  name: string;
  isin: string | null;
  ticker: string | null;
  kind: ProductKind;
  price_source: 'yahoo' | 'manual';
  source_id: string | null;
  ter: string | null;
  long_term: boolean;
};

export type ProductUpdate = Partial<
  Pick<ProductCreate, 'name' | 'isin' | 'ticker' | 'kind' | 'ter' | 'long_term'>
>;

export type Listing = { symbol: string; name: string | null; kind: ProductKind | null };

export type PricePreview = {
  symbol: string;
  name: string | null;
  exchange: string | null;
  price: string;
  currency: string;
  price_date: string;
  kind: ProductKind | null;
};

export type ProductPrice = {
  product_id: number;
  name: string;
  symbol: string | null;
  price: string | null;
  currency: string | null;
  date: string | null;
  fetched_at: string | null;
  stale: boolean;
};

export type PriceStatus = {
  last_refresh: string | null;
  stale: boolean;
  max_age_hours: number;
  products: ProductPrice[];
};

export type OperationKind = 'buy' | 'sell' | 'dividend' | 'fee';

export type Operation = {
  id: number;
  account_id: number;
  account_name: string;
  product_id: number;
  product_name: string;
  date: string;
  kind: OperationKind;
  shares: string; // "1.50000000"
  amount_eur: string;
  fee_eur: string | null;
};

export type OperationCreate = {
  account_id: number;
  product_id: number;
  date: string;
  kind: OperationKind;
  shares: string;
  amount_eur: string;
  fee_eur: string | null;
};

export type InvestmentImportRow = {
  row: number;
  date: string;
  product_id: number;
  product_name: string;
  kind: OperationKind;
  shares: string;
  amount_eur: string;
  fee_eur: string | null;
};

export type InvestmentImportResult = {
  read: number;
  new: number;
  duplicates: number;
  saved: boolean;
  errors: RowError[];
  operations: InvestmentImportRow[]; // las nuevas (hasta 200)
};

// Cartera (Fase 3, partes 3.4b y 3.4c). Porcentajes en tanto por uno: "0.071234" = 7,12 %
export type InvestmentSummary = {
  has_investments: boolean;
  as_of: string;
  value: string;
  cost: string;
  gain: string;
  gain_pct: string | null;
  realized: string;
  dividends: string;
  dividends_12m: string;
  fees: string;
  xirr: string | null;
  contributed_12m: string;
  contributions: { month: string; amount: string }[];
  streak: number;
  ter_annual: string;
  year_returns: { year: number; return_pct: string }[];
  max_drawdown: string | null;
  missing_prices: string[];
};

export type Position = {
  product_id: number;
  name: string;
  isin: string | null;
  symbol: string | null;
  kind: ProductKind;
  accounts: string[];
  shares: string;
  average_price: string | null;
  cost: string;
  price: string | null;
  price_currency: string | null;
  price_eur: string | null;
  price_date: string | null;
  fetched_at: string | null;
  stale: boolean;
  value: string | null;
  gain: string | null;
  gain_pct: string | null;
  weight: string | null;
  ter: string | null;
};

export type Positions = { total_value: string; items: Position[] };

export type BenchmarkItem = {
  key: string;
  name: string;
  symbol: string;
  available: boolean;
  value: string | null;
  diff: string | null; // índice − real (positivo: el índice habría ido mejor)
  xirr: string | null;
  price_date: string | null;
};

export type Benchmark = {
  has_investments: boolean;
  value: string;
  xirr: string | null;
  items: BenchmarkItem[];
};

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

type RequestOptions = { method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'; body?: unknown };

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

/** {month: "2026-09", q: undefined} → "?month=2026-09" (sin los vacíos). */
function queryString(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
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
  transactions: (filters: TransactionFilters = {}) =>
    request<TransactionPage>(`/api/transactions${queryString(filters)}`),
  updateTransaction: (id: number, changes: TransactionUpdate) =>
    request<Transaction>(`/api/transactions/${id}`, { method: 'PATCH', body: changes }),
  deleteTransaction: (id: number) => request<void>(`/api/transactions/${id}`, { method: 'DELETE' }),

  categories: () => request<Category[]>('/api/categories'),
  createCategory: (category: CategoryCreate) =>
    request<Category>('/api/categories', { method: 'POST', body: category }),
  updateCategory: (id: number, changes: Partial<CategoryCreate>) =>
    request<Category>(`/api/categories/${id}`, { method: 'PATCH', body: changes }),
  deleteCategory: (id: number) => request<void>(`/api/categories/${id}`, { method: 'DELETE' }),

  rules: () => request<Rule[]>('/api/rules'),
  /** Crea la regla o, si ya hay una con el mismo texto, la sustituye. */
  saveRule: (rule: { pattern: string; category_id: number | null; apply?: boolean }) =>
    request<RuleSaved>('/api/rules', { method: 'POST', body: rule }),
  updateRule: (id: number, changes: Partial<Pick<Rule, 'pattern' | 'category_id' | 'priority'>>) =>
    request<Rule>(`/api/rules/${id}`, { method: 'PATCH', body: changes }),
  deleteRule: (id: number) => request<void>(`/api/rules/${id}`, { method: 'DELETE' }),
  netWorth: (month?: string) =>
    request<NetWorth>(`/api/dashboard/net-worth${queryString({ month })}`),
  cashflow: (month?: string) =>
    request<Cashflow>(`/api/dashboard/cashflow${queryString({ month })}`),
  budgets: (month?: string) => request<Budgets>(`/api/budgets${queryString({ month })}`),
  saveBudgets: (items: BudgetChange[], month?: string) =>
    request<Budgets>(`/api/budgets${queryString({ month })}`, { method: 'PUT', body: { items } }),
  alerts: (month?: string) => request<Alerts>(`/api/alerts${queryString({ month })}`),
  recurring: (month?: string) =>
    request<RecurringSummary>(`/api/recurring${queryString({ month })}`),
  goal: (month?: string) => request<Goal>(`/api/goals${queryString({ month })}`),
  saveGoal: (name: string, targetAmount: string, month?: string) =>
    request<Goal>(`/api/goals${queryString({ month })}`, {
      method: 'PUT',
      body: { name, target_amount: targetAmount },
    }),
  deleteGoal: () => request<void>('/api/goals', { method: 'DELETE' }),
  backupStatus: () => request<BackupStatus>('/api/backups/status'),
  runBackup: () => request<BackupRun>('/api/backups/run', { method: 'POST' }),
  applyRules: (includeAuto: boolean) =>
    request<RulesApplied>(`/api/rules/apply${queryString({ include_auto: includeAuto })}`, {
      method: 'POST',
    }),

  products: () => request<Product[]>('/api/products'),
  searchProducts: (q: string) => request<Listing[]>(`/api/products/search${queryString({ q })}`),
  previewProduct: (symbol: string) =>
    request<PricePreview>(`/api/products/preview${queryString({ symbol })}`),
  createProduct: (product: ProductCreate) =>
    request<Product>('/api/products', { method: 'POST', body: product }),
  updateProduct: (id: number, changes: ProductUpdate) =>
    request<Product>(`/api/products/${id}`, { method: 'PATCH', body: changes }),
  deleteProduct: (id: number) => request<void>(`/api/products/${id}`, { method: 'DELETE' }),
  operations: (filters: { account_id?: number; product_id?: number } = {}) =>
    request<Operation[]>(`/api/investments/operations${queryString(filters)}`),
  createOperation: (op: OperationCreate) =>
    request<Operation>('/api/investments/operations', { method: 'POST', body: op }),
  updateOperation: (id: number, changes: Partial<OperationCreate>) =>
    request<Operation>(`/api/investments/operations/${id}`, { method: 'PATCH', body: changes }),
  deleteOperation: (id: number) =>
    request<void>(`/api/investments/operations/${id}`, { method: 'DELETE' }),
  /** Sin `confirm`: vista previa (no guarda). Con `confirm`: guarda todo o nada (`saved`). */
  importInvestments: (accountId: number, file: File, confirm: boolean) => {
    const form = new FormData();
    form.append('account_id', String(accountId));
    form.append('file', file);
    form.append('confirm', String(confirm));
    return request<InvestmentImportResult>('/api/investments/import', {
      method: 'POST',
      body: form,
    });
  },
  investmentSummary: () => request<InvestmentSummary>('/api/investments/summary'),
  positions: () => request<Positions>('/api/investments/positions'),
  benchmark: () => request<Benchmark>('/api/investments/benchmark'),
  priceStatus: () => request<PriceStatus>('/api/prices/status'),
  refreshPrices: () =>
    request<{ items: unknown[]; status: PriceStatus }>('/api/prices/refresh', { method: 'POST' }),
};
