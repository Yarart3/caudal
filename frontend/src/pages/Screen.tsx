import type { ReactNode } from 'react';
import { Logo } from '../Logo';

/** Tarjeta centrada con el logo: la base de las pantallas de entrada (como en la maqueta). */
export function Screen({ children, foot }: { children: ReactNode; foot?: ReactNode }) {
  return (
    <main className="login-wrap">
      <div className="login">
        <div className="row">
          <Logo />
          <span className="num" style={{ fontWeight: 700, fontSize: 20 }}>
            Caudal
          </span>
        </div>
        <div className="login-body">{children}</div>
        {foot && <p className="muted login-foot">{foot}</p>}
      </div>
    </main>
  );
}

export function Loading() {
  return (
    <Screen>
      <p className="muted">Cargando…</p>
    </Screen>
  );
}
