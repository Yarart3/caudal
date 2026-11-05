# Fase 3 · Patrimonio e inversiones

> **Versión:** `0.6.0` · **Fechas:** 2026-11-03 a 2026-11-05 · **Estado:** ✅ terminada (con los criterios que necesitan datos reales aplazados a la revisión final)

El objetivo de la Fase 3 es **ver todo tu dinero junto**: lo que tienes en las cuentas y lo que tienes invertido. Caudal guarda tus productos (ETF, acciones, planes…) y tus operaciones, descarga los precios solo, calcula las plusvalías (FIFO, como Hacienda), la rentabilidad real (TIR), la rentabilidad de cada año y la peor caída, y compara tu cartera con lo que habría pasado metiendo lo mismo en un indexado. La pestaña Patrimonio ya suma liquidez + inversiones.

Este documento explica **qué se ha hecho**, **cómo** y **por qué**, con apuntes para aprender cada concepto. La fase se hizo en 15 partes (3.1 a 3.7).

---

## Índice

1. [Resumen y estado](#1-resumen-y-estado)
2. [Decisiones de la fase](#2-decisiones-de-la-fase)
3. [Archivos nuevos y cambiados](#3-archivos-nuevos-y-cambiados)
4. [Parte 3.1: esquema de inversiones](#4-parte-31-esquema-de-inversiones)
5. [Partes 3.2a a 3.2c: precios](#5-partes-32a-a-32c-precios)
6. [Partes 3.3a a 3.3c: productos, operaciones y plantilla](#6-partes-33a-a-33c-productos-operaciones-y-plantilla)
7. [Partes 3.3d1 y 3.3d2: primeras pantallas](#7-partes-33d1-y-33d2-primeras-pantallas)
8. [Partes 3.4a a 3.4c: cálculos](#8-partes-34a-a-34c-cálculos)
9. [Parte 3.5: pestaña Inversiones](#9-parte-35-pestaña-inversiones)
10. [Parte 3.6: Patrimonio con inversiones](#10-parte-36-patrimonio-con-inversiones)
11. [Cierre: criterios de "hecho"](#11-cierre-criterios-de-hecho)
12. [Problemas encontrados y cómo se resolvieron](#12-problemas-encontrados-y-cómo-se-resolvieron)
13. [Chuleta de comandos y glosario](#13-chuleta-de-comandos-y-glosario)

---

## 1. Resumen y estado

| Parte | Qué | Commit | Estado |
|---|---|---|---|
| 3.1 | Migración `0004`: `products`, `investment_operations`, `prices`, `manual_valuations` | `add investments schema (products, operations, prices, manual valuations)` | ✅ |
| 3.2a | Cliente de Yahoo (precio, histórico, búsqueda) y `python -m app.prices` | `add Yahoo Finance price client and probe command` | ✅ |
| 3.2b | Migración `0005` (`exchange_rates`) y servicio de precios con divisas | `add price service with exchange rates (phase 3.2b)` | ✅ |
| 3.2c | Refresco automático y `GET /api/prices/status` · `POST /api/prices/refresh` | `add price refresh thread and prices api (phase 3, step 3.2c)` | ✅ |
| 3.3a | API de productos: buscador, vista previa del precio, alta, edición y borrado | `add products api with yahoo search and price check (phase 3, step 3.3a)` | ✅ |
| 3.3b | API de operaciones sin vender más de lo que se tiene | `add investment operations api with holdings check (phase 3, step 3.3b)` | ✅ |
| 3.3c | Plantilla Excel/CSV: descarga e importación con vista previa | `add investments template download and import with preview (phase 3, step 3.3c)` | ✅ |
| 3.3d1 | Pestaña Inversiones: cuentas, productos y operaciones | `add investments tab with accounts, products and operations (phase 3, step 3.3d1)` | ✅ |
| 3.3d2 | Pantalla de importar el historial | `add investments history import screen (phase 3, step 3.3d2)` | ✅ |
| 3.4a | `calc.py`: FIFO, TIR, rentabilidad por año, peor caída, aportaciones, racha y TER | `add fifo, xirr, yearly returns, drawdown and contributions calculations (phase 3, step 3.4a)` | ✅ |
| 3.4b | Cartera desde la BD y `GET /api/investments/summary` · `/positions` | `add portfolio positions and summary api (phase 3, step 3.4b)` | ✅ |
| 3.4c | Comparativa con IWDA / SXR8 / XEON y migración `0006` (`benchmark_prices`) | `add index benchmark comparison with stored benchmark prices (phase 3, step 3.4c)` | ✅ |
| 3.5 | Pestaña Inversiones completa | `add full investments tab with kpis, positions, contributions and benchmark (phase 3, step 3.5)` | ✅ |
| 3.6 | Patrimonio con inversiones | `add investments to net worth tab: stacked history, entities and type split (phase 3, step 3.6)` | ✅ |
| 3.7 | Cierre: documentación | `docs: close phase 3` | ✅ |

**Tests:** 623 en total (296 nuevos). ruff, ESLint, Prettier y el build, sin avisos.

---

## 2. Decisiones de la fase

### Productos y operaciones
- Tipo `commodity` (materia prima) para el oro, que es un ETC y no un ETF.
- La lista real de productos de Gerard **no se sube a git** (el repositorio es público).
- **Solo Yahoo** por ahora: todos los productos de Gerard son ETF o ETC. Morningstar (fondos) y CoinGecko (cripto) se añaden cuando haga falta; el esquema ya los admite (`price_source`).
- Plaza por defecto: **Xetra, en euros**. Buscar por ISIN en Yahoo da una sola cotización (Londres o Milán), así que el formulario deja escribir el símbolo de Xetra (`SXR8.DE`) y enseña su precio y divisa antes de guardar.
- Al crear un producto con precio de Yahoo se comprueba que el símbolo tiene precio y se toma su divisa; si Yahoo no responde, no se guarda. El símbolo no se cambia después. El tipo que propone Yahoo es orientativo (Stuttgart da `MUTUALFUND` para un ETF): decide el usuario.
- Operaciones: no se vende más de lo que hay **en esa cuenta**. El mismo día, las compras cuentan antes que las ventas. Se comprueba al crear, editar y borrar. Compras y ventas llevan participaciones; dividendos y comisiones, no. La fecha no puede ser futura y la comisión no puede superar el importe.
- **Importe en euros:** en una compra, lo que salió de la cuenta (comisiones incluidas); en una venta o un dividendo, lo que entró.
- «Duplicar operación» lo hace el formulario copiando los campos: no hay API propia.
- Las participaciones viajan en el JSON con 8 decimales fijos (`0.00000012`), nunca en notación científica.
- **Sin importador de RUMBO** (Gerard no lo ha usado) ni de Trade Republic o Scalable: las operaciones entran por el formulario o por la plantilla. No se ha copiado código de RUMBO.

### Plantilla
- El producto tiene que existir antes (crearlo desde la plantilla obligaría a adivinar el símbolo de Xetra). El `.xlsx` trae la hoja «Operaciones» vacía, instrucciones y un ejemplo inventado en otra hoja, que no se importa.
- Vista previa sin guardar y después confirmar; entra **todo o nada**, con la misma validación que el formulario. Huella por fila: el mismo archivo dos veces no duplica, y dos filas idénticas del mismo archivo entran las dos.
- Las operaciones escritas a mano no tienen huella: si luego se importa ese mismo historial, saldría repetido (la vista previa lo enseña antes de confirmar).

### Precios
- Cliente con `urllib` (biblioteca estándar), no con `httpx`: `httpx` solo está en la imagen de desarrollo y añadirlo obligaría a regenerar `uv.lock`. Solo viajan identificadores (símbolos), nunca cantidades.
- Tipos de cambio en su propia tabla (`exchange_rates`), sin usuario: son datos públicos. Símbolo `{DIVISA}EUR=X`; los precios en peniques (`GBp`/`GBX`) se guardan en libras.
- **Precio desactualizado** = se descargó (`fetched_at`) hace más de `PRICE_MAX_AGE_HOURS`; no se mira la fecha del precio. El sábado, el precio del viernes bajado hoy no está desactualizado.
- Refresco: al arrancar solo si algo falta o es antiguo; luego cada `PRICE_REFRESH_MIN`. Un símbolo que tengan varios usuarios se descarga una vez. Dos refrescos no se pisan (409). `PRICE_AUTO=false` lo apaga (los tests nunca salen a internet).
- Si se apunta una operación anterior al primer precio guardado, el siguiente refresco descarga el histórico desde esa fecha.
- Consultas desde la pantalla (buscar, comprobar precio): **un intento de 8 s**, para no dejar a nadie esperando casi un minuto. El refresco en segundo plano hace 3 intentos. El error técnico va al log; la pantalla dice «No se ha podido consultar Yahoo. Prueba en un momento.».

### Cálculos
- **FIFO por producto, sumando todas las cuentas**: un mismo ISIN en Trade Republic y en Scalable es un solo historial a efectos de Hacienda (criterio publicado; no es asesoría fiscal). La comprobación de no vender de más sigue siendo por cuenta.
- Coste del lote = importe de la compra. Un lote vendido a medias reparte su coste en proporción y redondea al céntimo; lo que queda se calcula por resta, así la suma siempre cuadra.
- **TIR propia** (Newton desde el 10 % y bisección de respaldo), con la convención de `XIRR` de Excel (días / 365). Sin `pyxirr`. La tasa se resuelve con `float` (no es un importe); los importes siguen en `Decimal`.
- **Rentabilidad por año natural con Dietz modificado** (no anualizada): una aportación grande en diciembre no cuenta como ganancia.
- **Peor caída** sobre la rentabilidad diaria encadenada, no sobre el valor: comprar más taparía las caídas. Para el valor diario, un dividendo es dinero que sale de la cartera y una comisión suelta, dinero que entra.
- Aportación del mes = compras − ventas. Racha = meses seguidos con aportación > 0; si este mes aún no hay, cuenta desde el anterior.
- Valor diario desde la primera operación con el último precio y tipo de cambio del día o anterior; antes del primer precio, lo que costó. Los productos manuales valen lo último anotado (la posición entera).
- Si a un producto le falta el precio de hoy, no suma en el valor ni en la plusvalía y sale en `missing_prices`; la TIR usa lo que costó.
- **Comparativa:** cada compra y venta se repite en el índice por el **mismo importe en euros** y en la misma fecha; si no llega para la venta, se vende todo. Dividendos y comisiones no se repiten (los tres índices son de acumulación). La diferencia está solo en el valor de hoy.
- Índices en euros de Xetra: MSCI World = `EUNL.DE` (el mismo fondo que IWDA, IE00B4L5Y983), S&P 500 = `SXR8.DE`, monetario = `XEON.DE`. Tabla propia `benchmark_prices` (datos públicos) que se actualiza con los precios. Si un índice no tiene cierres desde la primera compra (7 días de margen), sale «Sin datos».
- La API da los porcentajes en tanto por uno con 6 decimales (`"0.071234"` = 7,12 %).

### Pantallas
- «Mis posiciones»: una fila por **producto**, con las cuentas donde quedan participaciones. Etiqueta del precio: «~15 min» (de hoy), «Cierre» (de un día anterior), «A mano» y «Desactualizado».
- Orden de la pestaña: barra de precios, indicadores, posiciones, aportaciones · comparativa · dividendos, rentabilidad por año · riesgo y costes, el aviso de que no es asesoramiento y, debajo, lo de apuntar. Las operaciones enseñan las 10 últimas.
- «Intereses y dividendos» de la maqueta queda en **Dividendos**: los intereses de Trade Republic son movimientos de la cuenta de efectivo.
- Además de la maqueta (DISENO §7.5): «Rentabilidad por año» y «Riesgo y costes».
- **Patrimonio:** las inversiones se valoran al **final del mes elegido** (o hoy). Por entidad, cada cuenta suma su liquidez (verde) y lo invertido (azul); un producto en dos cuentas reparte su valor según las participaciones. El reparto por tipo junta los tipos de producto con «Fondo monetario» y «Efectivo» (la API los da en `investments_by_kind` para no cambiar `by_type`). El objetivo y sus hitos ya cuentan las inversiones.
- Commits con la fase al final: `… (phase 3, step 3.2c)` (petición de Gerard).

---

## 3. Archivos nuevos y cambiados

**Backend (nuevos):**
- `app/models/{product,investment_operation,price,manual_valuation,exchange_rate,benchmark_price}.py` y migraciones `0004_investments.py`, `0005_exchange_rates.py`, `0006_benchmark_prices.py`.
- `app/prices/`: `yahoo.py` (cliente), `service.py` (refrescar, pasar a euros, estado, índices), `auto.py` (hilo de refresco) y `__main__.py` (`probe` y `quote`).
- `app/investments/`: `operations.py` (validación), `holdings.py` (no vender de más), `importer.py` (plantilla), `calc.py` (FIFO, TIR, Dietz, caída, aportaciones), `portfolio.py` (cartera desde la BD y valor a una fecha) y `benchmark.py` (comparativa).
- `app/importers/plantilla_inversiones.py` (leer y generar la plantilla).
- `app/api/`: `prices.py`, `products.py`, `investments.py` (operaciones, plantilla, importar) y `portfolio.py` (resumen, posiciones, comparativa).
- Tests: `test_prices_{yahoo,service,auto,api}.py`, `test_products_api.py`, `test_investment_models.py`, `test_investment_operations_api.py`, `test_plantilla_inversiones.py`, `test_investments_import_api.py`, `test_investments_calc.py`, `test_portfolio.py`, `test_benchmark.py` y `test_net_worth_investments.py`.

**Backend (cambiados):** `app/main.py` (rutas y hilo de precios), `app/config.py` (`PRICE_AUTO`, `PRICE_REFRESH_MIN`, `PRICE_MAX_AGE_HOURS`), `app/dashboard/service.py` y `app/api/dashboard.py` (Patrimonio con inversiones).

**Frontend:** `pages/InvestmentsPage.tsx`; componentes `InvestmentAccountDialog`, `ProductDialog`, `OperationDialog`, `InvestmentImportCard` y `PortfolioOverview`; `investmentLabels.ts`; cambios en `api.ts`, `format.ts`, `styles.css`, `components/Charts.tsx` y `pages/PanelPage.tsx`.

---

## 4. Parte 3.1: esquema de inversiones

### Qué se hizo
Cuatro tablas: `products` (por usuario, ISIN único por usuario, fuente del precio y TER), `investment_operations` (cuenta, producto, fecha, tipo, participaciones `NUMERIC(18,8)` e importe en euros), `prices` (cierre diario por producto, `NUMERIC(18,6)`, con `fetched_at`) y `manual_valuations` (valor anotado a mano).

### Apuntes para aprender
- **ISIN:** código de 12 caracteres que identifica un valor (IE00B5BMR087). El mismo ISIN cotiza en varias bolsas con símbolos distintos (`SXR8.DE` en Xetra, `CSPX.L` en Londres).
- **`CHECK` en la base de datos:** reglas que la BD comprueba siempre (precio > 0, tipo válido). Aunque el código tenga un fallo, la BD no deja guardar datos imposibles.

---

## 5. Partes 3.2a a 3.2c: precios

### Qué se hizo
Cliente de la API no oficial de Yahoo (`/v8/finance/chart` para el precio y el histórico, `/v1/finance/search` para buscar) con lista de dominios permitidos, tiempo de espera y reintentos. El servicio guarda el histórico con `INSERT … ON CONFLICT DO UPDATE`, descarga los tipos de cambio que hagan falta y dice qué precios están desactualizados. Un hilo de la app refresca al arrancar (si hace falta) y cada `PRICE_REFRESH_MIN`.

Para probar desde la terminal:
```bash
docker compose run --rm tests python -m app.prices probe SXR8.DE
docker compose run --rm tests python -m app.prices quote SXR8.DE EUNL.DE XEON.DE
```

### Apuntes para aprender
- **`json.loads(..., parse_float=Decimal)`:** lee los números del JSON directamente como `Decimal`, sin pasar por `float` (que no representa bien 0,1).
- **Upsert (`ON CONFLICT DO UPDATE`):** insertar o, si la clave ya existe, actualizar. Así se puede volver a descargar un periodo sin duplicar.
- **Hilo en segundo plano con un `Lock`:** el candado evita que dos refrescos (el automático y el botón) trabajen a la vez.

---

## 6. Partes 3.3a a 3.3c: productos, operaciones y plantilla

### Qué se hizo
- **Productos:** buscador (ISIN, símbolo o nombre), vista previa del precio y alta solo si hay precio. Un producto con operaciones no se borra (409).
- **Operaciones:** CRUD con mensajes en castellano. Antes de guardar se repasa la cuenta entera en orden de fechas para no vender más de lo que hay (`holdings.first_shortfall`).
- **Plantilla:** `GET /api/investments/template?format=xlsx|csv` y `POST /api/investments/import` con `confirm=false` (vista previa) o `true` (guardar todo o nada).

### Apuntes para aprender
- **Validar contra la historia entera:** borrar una compra antigua puede dejar en negativo una venta posterior; por eso se comprueba toda la secuencia, no solo la operación nueva.
- **Transacción todo o nada:** se añaden todas las filas y se hace un solo `commit`; si algo falla, `rollback` y no queda nada a medias.
- **Huella (hash) por fila:** sha256 de los datos más el número de repetición de esa fila en el archivo; detecta reimportaciones sin confundir dos compras iguales.

---

## 7. Partes 3.3d1 y 3.3d2: primeras pantallas

### Qué se hizo
Pestaña Inversiones con cuentas de broker (Trade Republic como «inversiones y efectivo», Scalable como «inversiones»), productos con su último precio, operaciones con «+ Añadir compra / venta», «Duplicar» y «Editar», y la tarjeta «Importar historial» (descargar la plantilla, arrastrar el archivo, vista previa y confirmar).

### Apuntes para aprender
- **`FormData` y `multipart/form-data`:** cómo el navegador sube un archivo junto con otros campos.
- **Regla `react-refresh/only-export-components`:** un archivo de componentes solo debe exportar componentes; las constantes van aparte (`investmentLabels.ts`) para que la recarga en caliente funcione.

---

## 8. Partes 3.4a a 3.4c: cálculos

### Qué se hizo
- `calc.py`, sin base de datos: FIFO, TIR, Dietz, peor caída, aportaciones, racha y TER. 22 tests con casos hechos a mano y el ejemplo de la ayuda de `XIRR` de Excel (37,34 %).
- `portfolio.py`: lee de una vez operaciones, precios, tipos de cambio y valores manuales, y construye la serie diaria (5 años de 7 productos en unos 0,15 s).
- `benchmark.py`: repite las compras y ventas en los tres índices.

### Apuntes para aprender
- **FIFO (First In, First Out):** al vender, se consideran vendidas primero las participaciones más antiguas. Ejemplo: compras 10 a 100 € y 10 a 150 €; vendes 15 por 2.100 € → coste 1.000 + 750 = 1.750 → ganancia 350 €.
- **TIR / XIRR:** la tasa *r* que hace Σ flujo / (1 + r)^(días/365) = 0. Tiene en cuenta **cuándo** entra y sale cada euro. No tiene fórmula cerrada: se busca con **Newton** (rápido, puede fallar) y, si falla, con **bisección** (lenta pero segura).
- **Dietz modificado:** rentabilidad de un periodo con aportaciones: (V_fin − V_inicio − F) / (V_inicio + Σ F·peso), donde el peso es la parte del periodo que el dinero estuvo dentro.
- **Rentabilidad encadenada (time-weighted):** multiplica las rentabilidades de cada día quitando las aportaciones; mide cómo lo hicieron los productos, no cuánto metiste.
- **Peor caída (máximo drawdown):** la mayor bajada desde un máximo anterior.
- **TER:** comisión anual del fondo, ya descontada del precio. Coste estimado = valor × TER.

---

## 9. Parte 3.5: pestaña Inversiones

### Qué se hizo
Como la maqueta: barra de precios con «↻ Actualizar precios», 4 indicadores (valor, plusvalía, TIR y aportado en 12 meses con la racha), «Mis posiciones», aportaciones de 12 meses en barras, «¿Y si todo fuera a un indexado?», dividendos, rentabilidad por año, riesgo y costes, y el aviso de que no es asesoramiento.

### Apuntes para aprender
- **`Promise.all`:** pide los 7 datos de la pantalla a la vez y espera a todos; si uno falla, se enseña el error.
- **Formatear sin `-0,0 %`:** se redondea primero y se decide el signo con el número ya redondeado.

---

## 10. Parte 3.6: Patrimonio con inversiones

### Qué se hizo
`InvestmentHistory` carga los datos una vez y da el valor a cualquier fecha (total, coste, por cuenta y por tipo). `GET /api/dashboard/net-worth` suma las inversiones al patrimonio neto, a la evolución de 12 meses y a cada cuenta; la pantalla dibuja las barras apiladas, las entidades en azul y verde y el reparto por tipo.

### Apuntes para aprender
- **Valorar a una fecha:** repetir las operaciones hasta ese día y multiplicar por el último precio conocido. Es lo mismo que la serie diaria, pero solo para los días que hacen falta.

---

## 11. Cierre: criterios de "hecho"

- ✅ Modelos, precios con histórico y aviso de desactualizado, buscador, alta manual con «duplicar», plantilla, cálculos, pestaña Inversiones y Patrimonio con inversiones.
- ✅ Tests de FIFO (ventas parciales, redondeo, varias cuentas), XIRR (casos a mano y ejemplo de Excel), dividendos, precio desactualizado y divisas; aislamiento entre usuarios en cada endpoint nuevo.
- ✅ 623 tests, ruff, ESLint, Prettier y build sin avisos.
- ✅ La pestaña se parece a la maqueta (probado con datos inventados, en escritorio y en móvil).
- ⏳ **Aplazado (DISENO §17, pendiente 11):** «el valor de la cartera difiere menos del 1 % del que muestran los brokers el mismo día». Necesita las operaciones reales. Al revisarlo:
  - Apuntar el historial real (formulario o plantilla) y comparar el valor y las participaciones con Trade Republic y Scalable el mismo día.
  - Comprobar con Yahoo real la búsqueda, «Comprobar precio» y los índices de la comparativa (`quote EUNL.DE SXR8.DE XEON.DE`).
  - Con datos reales, comprobar que Inversiones y Patrimonio se parecen a la maqueta.

---

## 12. Problemas encontrados y cómo se resolvieron

| Problema | Causa | Solución |
|---|---|---|
| Un test de orden fallaba en el equipo de Gerard y aquí no | El orden de `ORDER BY name` depende de la intercalación (collation) de PostgreSQL | `ORDER BY lower(name)` |
| Algunas cotizaciones de Yahoo venían sin serie diaria | Yahoo lista plazas sin datos | Se tratan como «no encontrado» |
| Buscar por ISIN no daba la cotización de Xetra | Yahoo devuelve una sola plaza (Londres o Milán) | Se escribe el símbolo de Xetra y se comprueba su precio |
| Pydantic no validaba la fecha | Un campo llamado `date` tapaba el tipo `date` | Alias `Day = date` |
| Participaciones como `0E-8` en el JSON | `str(Decimal)` usa notación científica | Serializar con `format(v, "f")` |
| Un ISIN escrito en minúsculas daba error | Se validaba antes de pasarlo a mayúsculas | `AfterValidator` en el orden correcto |
| Un BOM literal (carácter invisible) en el código de la plantilla CSV | Se escribió el carácter tal cual | `codecs.BOM_UTF8` |
| Buscar en Yahoo tardaba casi un minuto si no respondía | 3 intentos con espera | Un intento de 8 s en las consultas desde la pantalla |
| «1 operaciónes» | Plural formado añadiendo «es» | Función `operations(n)` |
| La página se desplazaba en horizontal en el móvil (venía de la Fase 2) | Los textos `.sr-only` se colocaban donde estaría el texto (cabeceras anchas, barra de pestañas) | `top: 0; left: 0` en `.sr-only` |

---

## 13. Chuleta de comandos y glosario

```bash
docker compose run --rm tests                                   # todos los tests
docker compose run --rm tests ruff check .                      # lint del backend
docker compose run --rm tests ruff format --check .             # formato del backend
docker compose run --rm web                                     # lint y build del frontend
docker compose run --rm tests python -m app.prices probe SXR8.DE           # qué devuelve Yahoo
docker compose run --rm tests python -m app.prices quote SXR8.DE EUNL.DE   # precio y divisa
docker compose up -d --build                                    # reconstruir y arrancar
```

En la app, con la sesión iniciada: `http://localhost:8080/api/investments/summary`, `/api/investments/positions` y `/api/investments/benchmark` enseñan el JSON de la pestaña.

- **ETF / ETC:** fondo cotizado / producto cotizado sobre una materia prima (el oro).
- **De acumulación:** reinvierte los dividendos en lugar de pagarlos.
- **Plusvalía latente / realizada:** ganancia de lo que aún tienes / de lo que ya vendiste.
- **Precio medio:** lo que te costó de media cada participación que aún tienes (FIFO).
- **Peso:** parte de la cartera que es cada producto.
- **Xetra:** bolsa electrónica de Fráncfort; sus símbolos en Yahoo acaban en `.DE`.
- **Índice de referencia (benchmark):** con qué comparas tu cartera.
