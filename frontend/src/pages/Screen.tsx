import type { ReactNode } from 'react';
import { Logo } from '../Logo';

/** Pantalla centrada con una tarjeta y el logo, como las de entrada de la maqueta. */
export function Screen({ children }: { children: ReactNode }) {
  return (
    <main className="screen">
      <div className="card screen-card">
        <div className="row">
          <Logo />
          <span className="num" style={{ fontWeight: 700, fontSize: 20 }}>
            Caudal
          </span>
        </div>
        {children}
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
