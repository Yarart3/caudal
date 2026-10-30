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

// Aviso de «ha cambiado el estado de los backups» (copia manual desde Ajustes): el indicador de
// la cabecera se actualiza sin esperar a su próxima comprobación.
const BACKUP_EVENT = 'caudal:backup-changed';

export function notifyBackupChanged(): void {
  window.dispatchEvent(new Event(BACKUP_EVENT));
}

export function onBackupChanged(listener: () => void): () => void {
  window.addEventListener(BACKUP_EVENT, listener);
  return () => window.removeEventListener(BACKUP_EVENT, listener);
}
