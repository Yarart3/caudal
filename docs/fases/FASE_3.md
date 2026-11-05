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
| 3.4a | `app/investments/calc.py`: FIFO, TIR (XIRR), rentabilidad por año, peor caída, aportaciones, racha y TER (sin base de datos) | ✅ |
| 3.4b | Cartera desde la base de datos: posiciones, valor diario, plusvalías, indicadores y `GET /api/investments/summary` · `/positions` | ✅ |
| 3.4c | Comparativa con IWDA / SXR8 / XEON repitiendo los flujos y `GET /api/investments/benchmark` | ✅ |
| 3.5 | Pestaña Inversiones: indicadores, posiciones, aportaciones, comparativa, dividendos, rentabilidad por año y costes | ✅ |
| 3.6 | Patrimonio con inversiones: valor a fin de mes, evolución apilada, entidades con invertido + efectivo y reparto por tipo | ✅ |
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
- Orden de la pestaña: barra de precios, indicadores, «Mis posiciones», aportaciones · comparativa · dividendos, rentabilidad por año · riesgo y costes, el aviso de que no es asesoramiento y, debajo, lo de apuntar (operaciones, productos, importar y cuentas). Las operaciones enseñan las 10 últimas y un botón para verlas todas.
- «Intereses y dividendos» de la maqueta queda en **Dividendos**: los intereses de Trade Republic son movimientos de la cuenta de efectivo (pestaña Movimientos), no operaciones de inversión.
- Además de la maqueta (DISENO §7.5): tarjetas «Rentabilidad por año» (Dietz, el año en curso «hasta hoy») y «Riesgo y costes» (peor caída, plusvalía realizada, dividendos cobrados, comisiones de los fondos al año por TER y otras comisiones).
- Etiqueta del precio en las posiciones: «~15 min» si es de hoy, «Cierre» si es de un día anterior (la fecha, al pasar el ratón), «A mano» en los manuales y «Desactualizado» si falló el refresco. Si a un producto le falta precio, un aviso arriba dice que no cuenta en el valor.
- Importar en la pantalla: el archivo se sube dos veces (vista previa y confirmar) y no se guarda en ningún sitio. Con errores, el botón de importar queda desactivado y se listan las filas que fallan. Tras importar se actualizan los precios, para traer el histórico desde las compras antiguas.
- FIFO **por producto**, sumando todas las cuentas: un mismo ISIN en Trade Republic y en Scalable es un solo historial a efectos de Hacienda (criterio publicado; no es asesoría fiscal). La comprobación de no vender de más sigue siendo por cuenta.
- Coste del lote = importe de la compra (comisiones incluidas); lo cobrado en una venta ya va sin comisiones. Un lote vendido a medias reparte su coste en proporción y redondea al céntimo; lo que queda se calcula por resta, así la suma siempre cuadra.
- TIR propia (Newton desde el 10 % y bisección de respaldo), con la convención de `XIRR` de Excel (días / 365). Sin `pyxirr`: no hace falta otra dependencia. La tasa se resuelve con `float` (no es un importe); los importes siguen en `Decimal`.
- Rentabilidad por año natural con el método **Dietz modificado** (no anualizada): una aportación grande en diciembre no cuenta como ganancia. El año en curso, hasta hoy.
- Peor caída sobre la rentabilidad diaria encadenada, no sobre el valor: comprar más taparía las caídas. Para el valor diario, un dividendo es dinero que sale de la cartera y una comisión suelta, dinero que entra.
- Aportación del mes = compras − ventas. Racha = meses seguidos con aportación > 0; si este mes aún no hay, se cuenta desde el anterior (no se rompe a mitad de mes).
- «Mis posiciones»: una fila por **producto** (FIFO global), con las cuentas donde aún quedan participaciones. Si el mismo ETF está en dos brokers, sale una fila con los dos nombres.
- Valor diario desde la primera operación, con el último precio y tipo de cambio de ese día o anterior. Antes del primer precio, lo que costó. Los productos manuales valen lo último anotado (la posición entera).
- Si a un producto le falta el precio o el tipo de cambio de hoy, no suma en el valor ni en la plusvalía y sale en `missing_prices`; la TIR usa lo que costó, para no quedarse sin ella.
- Aportado en 12 meses = este mes y los 11 anteriores. La API da los porcentajes en tanto por uno con 6 decimales (`"0.071234"` = 7,12 %).
- Resumen y posiciones en su propio archivo (`app/api/portfolio.py`), con el mismo prefijo `/api/investments`: `investments.py` ya era largo.
- Comparativa: cada compra y venta se repite en el índice por el **mismo importe en euros** y en la misma fecha (cierre de ese día o el último anterior); si en el índice no llega para la venta, se vende todo. Dividendos y comisiones sueltas no se repiten (los tres índices son de acumulación). Como el dinero que entra y sale es el mismo, la diferencia está solo en el valor de hoy.
- Índices en euros de Xetra: MSCI World = `EUNL.DE` (el mismo fondo que IWDA, IE00B4L5Y983), S&P 500 = `SXR8.DE` y monetario = `XEON.DE`. Se guardan en su tabla `benchmark_prices` (datos públicos, para todos, como los tipos de cambio) y se actualizan con los precios, desde la primera operación de cualquier usuario. Si un índice no tiene cierres desde la primera compra (con 7 días de margen), sale «no disponible».
- Patrimonio: las inversiones se valoran al **final del mes elegido** (o hoy, si el mes no ha acabado), con las mismas reglas que la serie diaria (último precio del día o anterior; sin precio, lo que costó). Patrimonio neto = liquidez + inversiones; el objetivo y sus hitos ya lo usan.
- Por entidad: cada cuenta suma su liquidez (verde) y lo invertido en ella (azul). Un producto en dos cuentas reparte su valor según las participaciones de cada una (el FIFO sigue siendo por producto).
- Reparto por tipo: los tipos de producto con valor (ETFs, cripto, planes de pensiones…) junto a «Fondo monetario» y «Efectivo». La API los da aparte (`investments_by_kind`) para no cambiar `by_type`.
- Corregido de paso: los textos `.sr-only` (para lectores de pantalla) ensanchaban la página en el móvil cuando había pendientes de revisar o una tabla ancha; ahora van arriba a la izquierda.
- Refresco: al arrancar solo si algún precio falta o es antiguo; luego cada `PRICE_REFRESH_MIN` siempre (una petición por símbolo y divisa). Dos refrescos no se pisan.
- `POST /api/prices/refresh` actualiza solo los productos del usuario. `PRICE_AUTO=false` apaga el refresco automático (los tests lo apagan: nunca salen a internet).
