# Fase 3 · Patrimonio e inversiones

> **Versión:** `0.6.0` · **Inicio:** 2026-11-03 · **Estado:** 🔄 en curso

## Partes

| Parte | Qué | Estado |
|---|---|---|
| 3.1 | Migración `0004`: `products`, `investment_operations`, `prices`, `manual_valuations` | ✅ |
| 3.2a | `app/prices/yahoo.py`: precio, histórico y búsqueda por ISIN, y el comando `python -m app.prices` | ✅ |
| 3.2b | Migración `0005` (`exchange_rates`) y servicio de precios: histórico, divisas y aviso de precio desactualizado | ✅ |
| 3.2c | Refresco automático (al abrir y cada `PRICE_REFRESH_MIN`) y `GET /api/prices/status` · `POST /api/prices/refresh` | ✅ |
| 3.3a | API de productos: buscador, vista previa del precio, alta (comprueba el precio), edición y borrado | ✅ |
| 3.3b | API de operaciones: compra, venta, dividendo y comisión, sin vender más de lo que se tiene | ✅ |
| 3.3c | Plantilla Excel/CSV: descarga e importación del historial | ✅ |
| 3.3d1 | Pestaña Inversiones: cuentas de broker, productos (buscar, comprobar precio, guardar) y operaciones con «+ Añadir compra / venta», «duplicar» y editar | ✅ |
| 3.3d2 | Pestaña Inversiones: importar la plantilla (descargar, vista previa y confirmar) | ✅ |
| 3.4 | Cálculos: FIFO, plusvalías, XIRR, comparativa, TER, aportaciones | ⬜ |
| 3.5 | Pestaña Inversiones | ⬜ |
| 3.6 | Patrimonio con inversiones | ⬜ |
| 3.7 | Cierre | ⬜ |

## Decisiones

- Tipo de producto `commodity` (materia prima) para el oro, que es un ETC y no un ETF.
- `prices.fetched_at`: cuándo se descargó el precio, para avisar de precios desactualizados.
- La lista real de productos de Gerard no se sube a git (el repositorio es público).
- Solo Yahoo por ahora: todos sus productos son ETF o ETC. Morningstar (fondos) y CoinGecko (cripto) se añaden cuando haga falta; el esquema ya los admite.
- Cliente con `urllib` (biblioteca estándar) y no con `httpx`: `httpx` solo está en la imagen de desarrollo y añadirlo obligaría a regenerar `uv.lock`.
- Plaza por defecto: Xetra, en euros. Se ajusta al probar con `python -m app.prices`.
- Buscar por ISIN en Yahoo da una sola cotización (Londres o Milán), no la de Xetra: el formulario de productos (3.3) dejará escribir el símbolo y enseñará su precio y divisa antes de guardar.
- Tipos de cambio en su propia tabla (`exchange_rates`), sin usuario: son datos públicos. Símbolo `{DIVISA}EUR=X`; los precios en peniques (`GBp`/`GBX`) se guardan en libras.
- Precio desactualizado: se mira **cuándo se descargó** (`fetched_at`), no la fecha del precio. El sábado, el precio del viernes bajado hoy no está desactualizado.
- Un símbolo que tengan varios usuarios se descarga una sola vez.
- Commits como en las fases 1 y 2, con la fase al final: `… (phase 3, step 3.2c)` (petición de Gerard).
- Sin importador de RUMBO: Gerard no lo ha usado. Las operaciones entran por el formulario o por la plantilla.
- Productos: al crear uno con precio de Yahoo se comprueba que el símbolo tiene precio y se toma su divisa; si Yahoo no responde, no se guarda. El símbolo no se cambia después (se borra y se crea otro, si no tiene operaciones).
- El tipo que propone Yahoo es orientativo: Stuttgart da `MUTUALFUND` para un ETF. Decide el usuario.
- Si se apunta una operación anterior al primer precio guardado, el siguiente refresco descarga el histórico desde esa fecha.
- Operaciones: no se vende más de lo que hay **en esa cuenta** (comprar en Scalable y vender en Trade Republic no cuadra). El mismo día, las compras cuentan antes que las ventas. Se comprueba al crear, editar y borrar.
- Compras y ventas llevan participaciones; dividendos y comisiones, no. La fecha no puede ser futura y la comisión no puede superar el importe.
- «Duplicar operación» lo hace el formulario copiando los campos: no hay API propia.
- Las participaciones viajan en el JSON con 8 decimales fijos (`0.00000012`), nunca en notación científica.
- Plantilla: el producto tiene que existir antes (crear productos desde la plantilla obligaría a adivinar el símbolo de Xetra). El `.xlsx` trae la hoja «Operaciones» vacía, instrucciones y un ejemplo inventado en otra hoja, que no se importa.
- Importar: vista previa sin guardar y después confirmar; entra todo o nada, con la misma validación que el formulario y la comprobación de ventas. Huella por fila: el mismo archivo dos veces no duplica, y dos filas idénticas del mismo archivo entran las dos.
- Las operaciones escritas a mano no tienen huella: si luego se importa ese mismo historial, saldría repetido (la vista previa lo enseña antes de confirmar).
- Consultas a Yahoo desde la pantalla (buscar, comprobar precio, crear producto): un solo intento de 8 s, para no dejar a nadie esperando casi un minuto. El refresco en segundo plano sigue con 3 intentos. El error técnico va al log; la pantalla dice «No se ha podido consultar Yahoo. Prueba en un momento.».
- Indicadores, «Mis posiciones», aportaciones y comparativa llegan en la 3.5, cuando existan los cálculos (3.4).
- Importar en la pantalla: el archivo se sube dos veces (vista previa y confirmar) y no se guarda en ningún sitio. Con errores, el botón de importar queda desactivado y se listan las filas que fallan. Tras importar se actualizan los precios, para traer el histórico desde las compras antiguas.
- Refresco: al arrancar solo si algún precio falta o es antiguo; luego cada `PRICE_REFRESH_MIN` siempre (una petición por símbolo y divisa). Dos refrescos no se pisan.
- `POST /api/prices/refresh` actualiza solo los productos del usuario. `PRICE_AUTO=false` apaga el refresco automático (los tests lo apagan: nunca salen a internet).
