# Changelog de Caudal

Aquí se apunta qué se hace en cada fase. El formato está en `CLAUDE.md` (sección 9).

## [0.0.1] – 2026-10-01 · Fase 0
### Añadido
- Entorno preparado en el portátil y en el PC de casa: WSL2, Docker Desktop (sin arranque automático, WSL limitado a 4 GB), Git y VS Code con sus extensiones.
- Repositorio privado en GitHub (`Yarart3/Caudal`), clonado en `C:\Users\gerar\Proyectos\caudal`.
- Ejemplos con **datos inventados**: `samples/imagin_ejemplo.xlsx` (7 filas, con dos compras idénticas el mismo día y una transferencia a Wise) y `samples/wise_ejemplo.xlsx` (4 filas, con la pareja de esa transferencia y pagos con venta del fondo monetario).
- Carpetas de backup: `CaudalBackups/` en el pendrive `Gerard` y en `OneDrive - udl.cat\Proyectos\CaudalBackups`.
- README: sección "Trabajar desde varios ordenadores".
- `docs/fases/FASE_0.md`: qué se hizo en la fase, cómo, decisiones, problemas resueltos y apuntes para aprender.
- DISENO: sección 6.0 (el extracto se sube tal cual; columnas por nombre; comprobación de que el archivo es del banco de la cuenta elegida).
### Cambiado
- El pendrive mantiene su nombre de volumen, `Gerard` (`USB_LABEL=Gerard`), en lugar de `CAUDAL_BK`.
- Los commits se escriben en inglés (Conventional Commits).
- Formato de imagin confirmado: todo texto, fecha `dd/mm/aaaa`, importes con dos decimales, conceptos en catalán y a veces en minúsculas (`BIZUM ENVIAT`, `BIZUM REBUT`, `enviament de dine`). Reglas de Bizum actualizadas.
- Formato de Wise confirmado: columna `Fecha y hora`, celdas vacías como texto vacío, venta del fondo en la misma fila que el pago, ingreso desde imagin como `CREDIT` + `DEPOSIT` con `imaginBank` en `Referencia del pago`.
- **Trade Republic y Scalable se llevan a mano** (sin importadores): efectivo de Trade Republic en Movimientos y compras y ventas con el formulario, con "duplicar operación" y posición inicial por producto.
- Fase 1b: las filas que no se pueden leer se listan con su error y se pueden añadir a mano (`errors` en `/api/imports`).
### Notas
- Pendiente de Gerard: elegir la contraseña de backup y apuntarla en papel antes de la Fase 1d.
- La cuenta de OneDrive de la UdL caducará al acabar la carrera: antes, cambiar `ONEDRIVE_DIR` (pendiente 7 de DISENO).
- Las capturas del README (`docs/capturas/`) se harán en la Fase 7.

## [0.0.0] – 2026-10-01 · Diseño
### Añadido
- Documento de diseño (`docs/DISENO.md`) con las decisiones, el modelo de datos, la lógica, los backups, la seguridad y el roadmap.
- Maqueta de referencia con tres pestañas: Patrimonio, Movimientos e Inversiones (`maqueta/caudal-maqueta.html`).
- `README.md`, `CLAUDE.md` e `INSTRUCCIONES_PROYECTO_CLAUDE.md`.
### Notas
- Pendiente para la Fase 0: ruta de OneDrive, ejemplos inventados de imagin y Wise, y comprobar si la `Fecha` de imagin es fecha o texto.
- Pendiente para la Fase 3: qué exportan Trade Republic y Scalable.
