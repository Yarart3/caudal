// Aviso de «han cambiado los datos» (importar, editar, categorizar…). Lo escucha, por ejemplo,
// el contador de «por revisar» de la barra lateral para actualizarse sin recargar la página.

const EVENT = 'caudal:data-changed';

export function notifyDataChanged(): void {
  window.dispatchEvent(new Event(EVENT));
}

export function onDataChanged(listener: () => void): () => void {
  window.addEventListener(EVENT, listener);
  return () => window.removeEventListener(EVENT, listener);
}
