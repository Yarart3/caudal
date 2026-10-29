import { useEffect, useId, useRef, type ReactNode } from 'react';

/**
 * Ventana modal con el <dialog> del navegador: atrapa el foco, se cierra con Esc y deja el
 * resto de la página inerte. Se monta abierta; para cerrarla, quien la usa deja de pintarla.
 */
export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
    // Sin cerrar en la limpieza: al desmontarse, el <dialog> sale del DOM y se cierra solo
  }, []);

  return (
    <dialog ref={ref} className="modal" aria-labelledby={titleId} onClose={onClose}>
      <div className="between">
        <h2 id={titleId}>{title}</h2>
        <button type="button" className="link-btn" onClick={onClose} aria-label="Cerrar">
          ✕
        </button>
      </div>
      {children}
    </dialog>
  );
}
