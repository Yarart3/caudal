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

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

type RequestOptions = { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; body?: unknown };

async function request<T>(path: string, { method = 'GET', body }: RequestOptions = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
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
};
