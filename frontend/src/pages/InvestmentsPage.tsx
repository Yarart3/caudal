import { AppShell } from '../AppShell';

/** Pestaña Inversiones: vacía hasta la Fase 3 (DISENO 3.3). */
export function InvestmentsPage() {
  return (
    <AppShell title="Inversiones" current="Inversiones" tabs>
      <section className="card empty">
        <h2>Todavía no hay inversiones</h2>
        <p className="muted">
          Aquí verás tu cartera: lo que vale, cuánto has ganado, tus aportaciones y la comparación
          con un indexado.
        </p>
        <p className="muted">
          Pronto podrás apuntar tus compras y ventas de ETFs y cripto. De momento, el efectivo de
          tus cuentas ya cuenta en Patrimonio.
        </p>
      </section>
    </AppShell>
  );
}
