# Fase 1b · Importadores de imagin y Wise

> **Versión:** `0.2.0` · **Fechas:** 2026-10-19 → 2026-10-21 · **Estado:** ✅ terminada

El objetivo de la Fase 1b es **importar los extractos reales de imagin y Wise** sin duplicados y sin inflar los gastos con las transferencias entre cuentas propias. Las filas que no se pueden leer nunca se pierden en silencio: se enseñan y se pueden apuntar a mano.

Este documento explica **qué se ha hecho**, **cómo** y **por qué**, con apuntes para aprender cada concepto. La fase se hizo en una preparación (los ejemplos) y 5 partes, cada una probada y guardada con su commit, sobre todo en el Mac.

---

## Índice

1. [Resumen y estado](#1-resumen-y-estado)
2. [Cómo trabajamos en esta fase](#2-cómo-trabajamos-en-esta-fase)
3. [Archivos nuevos y cambiados](#3-archivos-nuevos-y-cambiados)
4. [Antes de empezar: los ejemplos](#4-antes-de-empezar-los-ejemplos)
5. [Parte 1.1: leer los extractos](#5-parte-11-leer-los-extractos)
6. [Parte 1.2: huella y guardado sin duplicados](#6-parte-12-huella-y-guardado-sin-duplicados)
7. [Parte 1.3: transferencias internas](#7-parte-13-transferencias-internas)
8. [Parte 1.4: API de importar y alta manual](#8-parte-14-api-de-importar-y-alta-manual)
9. [Parte 1.5: pantalla Importar](#9-parte-15-pantalla-importar)
10. [Cierre: criterios de "hecho"](#10-cierre-criterios-de-hecho)
11. [Decisiones de la fase](#11-decisiones-de-la-fase)
12. [Problemas encontrados y cómo se resolvieron](#12-problemas-encontrados-y-cómo-se-resolvieron)
13. [Chuleta de comandos](#13-chuleta-de-comandos)
14. [Glosario](#14-glosario)

---

## 1. Resumen y estado

| Parte | Qué | Commit | Estado |
|---|---|---|---|
| — | `samples/imagin_ejemplo.xlsx` rehecho (texto, dos decimales, saldos que cuadran) | `e57be3b` | ✅ |
| 1.1 | Lectores de imagin y Wise, sin BD (`app/importers/`) + openpyxl | `21b6e2a` | ✅ |
| 1.2 | Huella anti-duplicados y guardado con `ON CONFLICT DO NOTHING` | `9dbffdd` | ✅ |
| 1.3 | Emparejado de transferencias internas (`app/transfers/`) | `a7a9492` | ✅ |
| 1.4 | `POST /api/imports` y `POST /api/transactions` + python-multipart | `5a27985` | ✅ |
| 1.5 | Pantalla Importar con alta manual de las filas con error | `efdc156` | ✅ |
| Cierre | Criterios de "hecho", CHANGELOG `0.2.0`, README, DISENO y CLAUDE.md | — | ✅ |

**Tests:** 97 en total (66 nuevos en esta fase). ruff, ESLint, Prettier y el build, sin avisos.

---

## 2. Cómo trabajamos en esta fase

Igual que en la 1a: partes pequeñas, cada una con sus archivos completos (bloques `cat > … <<'EOF'` pegados en la terminal), sus comprobaciones (`wc -l`, pytest, ruff) y su commit en `main`.

Dos cosas nuevas:
- **Primero los ejemplos, después el código.** Antes de escribir el importador se revisaron los ejemplos de `samples/` y se rehízo el de imagin para que cubriera todos los casos de prueba (sección 4).
- **Los casos que los ejemplos no cubren** (fila con un importe roto, Wise en dólares, salto de saldo…) se prueban con **Excel pequeños que crean los propios tests** con openpyxl, con las mismas cabeceras que los reales. Así no hace falta llenar `samples/` de casos raros.

---

## 3. Archivos nuevos y cambiados

```text
backend/
├── pyproject.toml · uv.lock          ← + openpyxl 3.1.5, python-multipart 0.0.32
├── app/
│   ├── main.py                       ← registra los routers imports y transactions
│   ├── api/
│   │   ├── imports.py                ← POST /api/imports                       (1.4)
│   │   └── transactions.py           ← POST /api/transactions (alta manual)    (1.4)
│   ├── importers/
│   │   ├── __init__.py               ← registro: get_importer, detect_format, check_format (1.1)
│   │   ├── base.py                   ← interfaz, filas, normalización, saldo   (1.1)
│   │   ├── imagin.py · wise.py       ← un importador por banco                 (1.1)
│   │   ├── fingerprint.py            ← huella anti-duplicados                  (1.2)
│   │   └── service.py                ← import_statement(): leer + guardar + emparejar (1.2–1.3)
│   └── transfers/
│       ├── __init__.py
│       └── matcher.py                ← emparejar transferencias internas       (1.3)
└── tests/
    ├── conftest.py                   ← + fixture make_account                  (1.2)
    ├── test_importers.py             ← lectura (31 tests)                      (1.1)
    ├── test_import_service.py        ← huella y guardado (10)                  (1.2)
    ├── test_transfers.py             ← transferencias (12)                     (1.3)
    └── test_imports_api.py           ← API y aislamiento (13)                  (1.4)
frontend/src/
├── api.ts                            ← tipos y llamadas nuevas; admite FormData (1.5)
├── format.ts                         ← euros, fechas e importes a la española  (1.5)
├── AppShell.tsx                      ← barra lateral + cabecera comunes        (1.5)
├── App.tsx                           ← ruta /importar                          (1.5)
├── pages/PanelPage.tsx               ← usa AppShell + botón Importar extracto  (1.5)
├── pages/ImportPage.tsx              ← pantalla Importar                       (1.5)
└── styles.css                        ← estilos de la maqueta para importar     (1.5)
docker-compose.yml                    ← el servicio tests monta ./samples en /samples
samples/imagin_ejemplo.xlsx           ← rehecho
```

---

## 4. Antes de empezar: los ejemplos

### Qué se hizo

Al revisar los ejemplos de la Fase 0 salieron varios problemas:

- **imagin:**
  - tres fechas eran fechas de Excel en vez de texto, porque al editarlas en Excel las convirtió;
  - había importes sin dos decimales (`-23EUR`, `-0,5EUR`), cuando imagin siempre los da con dos;
  - los saldos no cuadraban entre filas;
  - no había dos compras iguales el mismo día;
  - la transferencia a Wise (`-0,50`) no tenía pareja en el ejemplo de Wise, que trae un `+50`.
- **Wise:** el del repositorio estaba bien. Se adjuntó otro que parecía sacado de un extracto real con pocos cambios; no se usó ni se subió.

Se rehízo `samples/imagin_ejemplo.xlsx` con 8 filas inventadas, todas en texto, del más reciente al más antiguo y con los saldos encadenados:

| Fila | Concepto | Fecha | Importe | Saldo | Para qué está |
|---|---|---|---|---|---|
| 2 | WWW.AMAZON | 29/09/2026 | -69,73EUR | 67,23EUR | compra |
| 3 | BIZUM ENVIAT | 27/09/2026 | -8,20EUR | 136,96EUR | Bizum enviado |
| 4 | enviament de dine | 27/09/2026 | -50,00EUR | 145,16EUR | pareja del `+50` de Wise |
| 5 | MERCADONA | 27/09/2026 | -2,45EUR | 195,16EUR | dos compras iguales… |
| 6 | MERCADONA | 27/09/2026 | -2,45EUR | 197,61EUR | …el mismo día |
| 7 | BIZUM REBUT | 26/09/2026 | 2,00EUR | 200,06EUR | Bizum recibido |
| 8 | BON AREA | 26/09/2026 | -1,94EUR | 198,06EUR | compra |
| 9 | TRANSFER IMMEDIATA | 25/09/2026 | 150,00EUR | 200,00EUR | transferencia recibida |

### Apuntes para aprender

- **Excel "ayuda" demasiado:** al escribir `27/09/2026` en una celda, Excel la convierte en fecha. Para que se quede como texto, hay que poner un apóstrofo delante (`'27/09/2026`) o dar formato Texto a la celda antes de escribir.
- **Un ejemplo inventado tiene que ser coherente**, no solo tener la forma correcta: si los saldos no cuadran, el importador avisa (con razón) y el ejemplo deja de servir para comprobar que "el saldo cuadra".
- **Datos reales:** un extracto con comercios con su población, el nombre del titular y saldos que cuadran fila a fila probablemente es real. No se sube al repositorio ni se pega en ningún chat.

---

## 5. Parte 1.1: leer los extractos

### Qué se hizo

- **`base.py`**, las piezas comunes:
  - `Importer`, la interfaz de cada banco: `detect(workbook)`, `missing_columns(workbook)` y `parse(workbook) -> ParseResult`.
  - `ParseResult` lleva los movimientos (`ParsedTransaction`), las filas con error (`RowError`: fila, columna, dato y mensaje), los avisos de saldo y el saldo final del extracto.
  - `Row`: acceso a una fila **por nombre de columna**. Una celda vacía y un texto vacío (`''`) cuentan igual.
  - `parse_date`: acepta `dd/mm/aaaa` en texto, fecha de Excel o número de serie de Excel.
  - `parse_es_amount`: `-1.234,56EUR` → `Decimal('-1234.56')`.
  - `to_money`: número de Excel → `Decimal`.
  - `normalize_text`: mayúsculas, sin acentos y con un solo espacio.
  - `check_balance_chain`: comprueba fila a fila que el saldo anterior más el importe da el saldo del extracto, en los dos sentidos.
- **`imagin.py`:** lee `Concepto`, `Fecha`, `Importe` y `Saldo`. El concepto se guarda tal cual, también en minúsculas (`enviament de dine`).
- **`wise.py`:**
  - Lee la hoja `All transactions`.
  - Concepto: `Comercio` → beneficiario (si es gasto) o pagador (si es ingreso) → `Descripción`.
  - Solo EUR. Si el signo no coincide con `DEBIT`/`CREDIT`, la fila va a errores.
  - Saca dos pistas de transferencia: `imagin` (un `CREDIT` + `DEPOSIT` con `imaginBank` en la referencia) y `conversion` (`Cambiar desde` / `Cambiar a`).
  - Las columnas del fondo se ignoran.
- **`__init__.py`:** `check_format(workbook, banco)` comprueba, antes de leer nada, que el archivo es del banco de la cuenta: *"Este archivo parece de Wise, pero has elegido una cuenta de imagin"*. Si solo falta una columna, lo dice: *"No se encuentra la columna «Importe»"*.

### Apuntes para aprender

- **Por qué openpyxl y no pandas:** pandas decide los tipos por su cuenta (convierte fechas, pasa importes a `float`, `''` a `NaN`). Aquí interesa justo lo contrario: ver cada celda tal cual, para distinguir un texto `29/09/2026` de una fecha de Excel, y no tocar nunca un `float`.
- **`Decimal(str(x))` y no `Decimal(x)`:** `Decimal(664.35)` da `664.349999999999…`, porque convierte el `float` exacto que hay en memoria. En cambio, `str(664.35)` da `'664.35'` (la representación más corta), y de ahí sale el `Decimal` correcto.
- **`quantize(Decimal("0.01"))`:** fija dos decimales. Si al cuantizar cambia el valor, es que traía más decimales y no es un importe en euros.
- **Leer por nombre de columna:** si el banco añade o mueve columnas, el importador sigue funcionando. Si quita una necesaria, el mensaje dice exactamente cuál.
- **Errores por fila en vez de excepciones:** una fila rota no debe tirar la importación entera. Se recoge en `errors` y se sigue con la siguiente.
- **`dataclass(frozen=True)`:** objetos inmutables; `dataclasses.replace()` crea una copia con un campo cambiado.

---

## 6. Parte 1.2: huella y guardado sin duplicados

### Qué se hizo

- **`fingerprint.py`**, la huella de cada movimiento (SHA-256, 64 caracteres):
  - Wise: `sha256(cuenta | id | Documento de identidad)`.
  - imagin: `sha256(cuenta | fecha | importe | concepto normalizado | saldo)`.
- **`service.py`**, `import_statement(db, cuenta, bytes)`:
  1. Comprueba que la cuenta tiene banco.
  2. Abre el archivo, comprueba que es del banco de la cuenta y lo lee.
  3. Inserta todo en **una sola sentencia** con `ON CONFLICT DO NOTHING` y `RETURNING`.
  4. Actualiza el saldo de referencia de la cuenta y hace commit.
  - Devuelve `ImportSummary`: leídos, nuevos, ya existían, por revisar, internos, errores, avisos y saldo final.
- **Fixture `make_account`** en `conftest.py`.
- No hizo falta migración: la columna `fingerprint` y la restricción única `(account_id, fingerprint)` ya existían desde la 1a.

### Apuntes para aprender

- **`INSERT … ON CONFLICT DO NOTHING RETURNING id`:** PostgreSQL inserta las filas nuevas, se salta en silencio las que chocarían con la restricción única y devuelve solo las insertadas. Contar lo devuelto da "nuevos", y el resto son "ya existían". Es atómico: no hay carrera entre "comprobar si existe" e "insertar".
- **Por qué el saldo en la huella de imagin:** dos compras de `-2,45` en MERCADONA el mismo día tienen la misma fecha, concepto e importe. Lo único que las distingue es el saldo que queda después de cada una.
- **`NULL` en una restricción única:** en PostgreSQL, dos `NULL` no se consideran iguales. Por eso los movimientos a mano (sin huella) nunca chocan entre sí.
- **Saldo de referencia "que no rebobina":** si importas un extracto de agosto después de uno de octubre, el saldo de la cuenta debe seguir siendo el de octubre. Solo se actualiza si el extracto llega a una fecha igual o posterior.

---

## 7. Parte 1.3: transferencias internas

### Qué se hizo

- **`transfers/matcher.py`** busca pareja a cada movimiento recién importado entre **todos** los movimientos del usuario:
  - de otra cuenta, con el importe opuesto, como mucho a 3 días y todavía libre;
  - y **confirmado** por la pista del extracto (Wise dice `imaginBank` y la otra pata es de una cuenta imagin) o por un concepto de transferencia en alguna pata (`TRANSFER`, `ENVIAMENT`, `TRASPAS`).
- Se marcan las dos patas (`is_internal_transfer`) y, si estaban "por revisar", pasan a `auto`, sin categoría.
- Las conversiones de divisa de Wise se marcan siempre como internas.
- `service.py` llama al emparejador después de insertar, antes del commit.

### Apuntes para aprender

- **Falsos positivos frente a falsos negativos:** marcar como transferencia algo que no lo es **esconde un gasto** (error grave e invisible). No marcar una transferencia la deja a la vista, y el usuario la corrige. Por eso se exige una confirmación además del importe y la fecha.
- **Solo lo nuevo:** si se buscaran parejas en todo cada vez, una pareja que el usuario desmarcó se volvería a marcar sola en la siguiente importación.
- **`db.flush()`:** envía los cambios a PostgreSQL dentro de la transacción, sin hacer commit. Así, la siguiente búsqueda ya ve la pareja como ocupada y un movimiento no se empareja dos veces.
- **El filtro por usuario va en la consulta** (`Account.user_id == user_id`): la salida de imagin de los padres nunca puede ser pareja del Wise de Gerard.

---

## 8. Parte 1.4: API de importar y alta manual

### Qué se hizo

- **`POST /api/imports`** (multipart: `account_id` y `file`):
  - Si la cuenta es de otro usuario: 404.
  - Lee como mucho 5 MB + 1 byte; si pasa de 5 MB, 413.
  - Archivo vacío o que no se puede importar: 422 con el mensaje en castellano, y no se guarda nada.
  - El archivo no se guarda nunca (DISENO 8.3).
- **`POST /api/transactions`:** alta manual.
  - Valida la cuenta (404 si es de otro), la fecha, el concepto (1 a 200 caracteres) y el importe (2 decimales como mucho).
  - Sin huella.
  - Busca pareja de transferencia, para que un ingreso apuntado a mano en Trade Republic se empareje con la salida de imagin.
- **Dependencia `python-multipart`**, que FastAPI necesita para `Form` y `UploadFile`.

### Apuntes para aprender

- **multipart/form-data:** es la forma de enviar archivos en un formulario. El cuerpo va en partes separadas por un *boundary*, una para `account_id` y otra para el archivo. El `Content-Type` con el boundary lo pone el navegador; por eso `api.ts` no lo fija cuando envía un `FormData`.
- **`file.file.read(MAX + 1)`:** leer un byte más del límite basta para saber si se pasa, sin cargar en memoria un archivo de 2 GB.
- **Zip bomb:** un `.xlsx` es un zip. Uno malicioso puede pesar poco comprimido y muchísimo descomprimido. El límite de 5 MB y la lectura en modo `read_only` de openpyxl reducen el riesgo. Además, la app solo es accesible en la red de casa.
- **Códigos de estado:** 404 (no es tuyo o no existe), 413 (demasiado grande), 422 (el contenido no es válido).

---

## 9. Parte 1.5: pantalla Importar

### Qué se hizo

- **`AppShell.tsx`:** la barra lateral y la cabecera salen de `PanelPage` y se usan en todas las pantallas con sesión. *Patrimonio* lleva al panel y *Movimientos* a `/importar`. Inversiones y Ajustes siguen desactivados.
- **`ImportPage.tsx`**, como la sección "Importar extracto bancario" de la maqueta:
  - **Izquierda:** cuenta y zona para arrastrar el archivo. Muestra el resumen (barra de nuevos sobre leídos y los recuentos), el saldo según el extracto, los avisos de saldo y la tabla de filas con error con **Añadir a mano**. Si no hay cuentas con banco, permite crear la de imagin o Wise (las de Wise como "fondo monetario").
  - **Derecha:** *Añadir movimiento manual* (Gasto/Ingreso, concepto, fecha, importe a la española y cuenta). Si se viene de **Añadir a mano**, dice qué fila falló y elige su cuenta.
- **`format.ts`:**
  - `formatEur`: `1.234,50 €`, con `useGrouping: 'always'`.
  - `formatDate`: `29/09/2026`.
  - `parseEsAmount`: `12,50` → `"12.50"`, sin pasar por `float`.
- Probado en Chromium contra el backend real: importar, reimportar (0 nuevos), banco equivocado, Wise con transferencia interna, fila rota y alta manual. Sin errores en la consola y sin scroll horizontal en móvil.

### Apuntes para aprender

- **Arrastrar y soltar:** hay que llamar a `preventDefault()` en `dragover` (si no, el navegador abre el archivo) y leer `event.dataTransfer.files` en `drop`. El `<label htmlFor>` hace que un clic en la zona abra el selector del `<input type="file">` oculto.
- **`input.value = ''` después de subir:** si no, elegir **el mismo archivo** otra vez no dispara `onChange`. Y reimportar el mismo archivo es justo lo que se prueba.
- **`key` para reiniciar un componente:** `<ManualCard key={pending.key}>` hace que React cree el formulario de cero cuando cambia la fila pendiente, sin un `useEffect` que copie props al estado.
- **El dinero viaja como texto:** el JSON trae `"-14.50"`. Solo se pasa a `Number` para pintarlo con `Intl`; las cuentas las hace el backend con `Decimal`.

---

## 10. Cierre: criterios de "hecho"

| Criterio (CLAUDE.md, Fase 1b) | Cómo se comprobó | Resultado |
|---|---|---|
| Importar dos veces el mismo archivo da 0 nuevos | `test_import_imagin_twice_gives_zero_new`, `test_import_and_reimport` y en la pantalla: la segunda vez sale «0 nuevos · 8 ya existían» | ✅ |
| El saldo cuadra con el extracto | La comprobación fila a fila no da avisos con los ejemplos; la suma de los movimientos de imagin (17,23 €) es el saldo final menos el inicial (67,23 − 50,00), y el saldo de referencia de la cuenta queda en 67,23 € | ✅ |
| Una recarga imagin → Wise queda marcada como interna | `test_imagin_then_wise` / `test_wise_then_imagin`, y en la pantalla: «1 transferencia interna» al importar Wise | ✅ |
| Los tests pasan | `docker compose run --rm tests` → **97 passed**; ruff, ESLint, Prettier y build sin avisos | ✅ |
| Tests con `samples/`: lectura, signos, duplicados, compras iguales, emparejado y fila ilegible en `errors` sin abortar | `test_importers.py`, `test_import_service.py`, `test_transfers.py` | ✅ |

---

## 11. Decisiones de la fase

Todas están ya pasadas a DISENO, CLAUDE.md, README o CHANGELOG.

| Decisión | Motivo | Dónde está |
|---|---|---|
| Solo openpyxl, sin pandas ni xlrd | Ver cada celda tal cual y no pasar por `float`; ningún banco da `.xls` | DISENO §10, CLAUDE.md §3 |
| `parse()` devuelve `ParseResult` (movimientos + errores + avisos + saldo final), no solo la lista | Las filas con error y los avisos tienen que llegar a la pantalla | CLAUDE.md §7 |
| Huella de Wise = `sha256(cuenta | ID)` | Longitud fija de 64 caracteres; no depender de la longitud de los ID de Wise | DISENO §9.2 |
| Transferencias: concepto o pista **obligatorios** | Un `-12,40` con tarjeta y un `+12,40` de una devolución no deben esconderse como transferencia | DISENO §9.3 |
| Internas → `auto` sin categoría (respetando una categoría manual) | No son gasto ni ingreso: no deben quedar «por revisar» | DISENO §9.3 |
| Solo se busca pareja a lo recién importado o apuntado | Si el usuario desmarca una pareja, no vuelve a marcarse sola | DISENO §9.3 |
| Conversiones de divisa de Wise = internas sin pareja | Mover dinero entre divisas propias no es gasto | DISENO §9.3 |
| Saldo de referencia = último saldo del extracto, salvo que el extracto sea más antiguo | Patrimonio (1c) parte de ahí; un extracto viejo no debe rebobinar la cuenta | DISENO §10 |
| Máximo 5 MB por archivo | Un año de extracto ocupa cientos de KB; evita llenar la memoria | DISENO §10, CLAUDE.md §6 |
| `POST /api/transactions` adelantado a la 1b | Lo necesita «Añadir a mano» | CLAUDE.md §6, DISENO §10 |
| Pantalla Importar en `/importar`; crear cuenta desde ahí | La pestaña Movimientos llega en la 1c y Ajustes → Cuentas después | DISENO §10 |
| Los casos raros se prueban con Excel creados en los tests | `samples/` se queda pequeño y realista | Esta carpeta |
| **Pendiente:** con el primer extracto real de Wise, mirar si salen tipos de fila nuevos | Los ejemplos solo tienen pagos con tarjeta e ingresos | DISENO §17 (pendiente 10) |

---

## 12. Problemas encontrados y cómo se resolvieron

| Problema | Causa | Solución |
|---|---|---|
| El ejemplo de imagin no cubría los casos de prueba | Se hizo a mano en la Fase 0 y Excel convirtió fechas; los saldos no se encadenaban | Rehacerlo con 8 filas inventadas, todas en texto y coherentes (sección 4) |
| Se adjuntó un ejemplo de Wise que parecía real | Copiado de un extracto con pocos cambios | No usarlo; seguir con el del repositorio |
| Los tests no encontraban `samples/` | El servicio `tests` solo montaba `./backend` | `- ./samples:/samples:ro` en `docker-compose.yml` |
| `ruff format --check`: *1 file would be reformatted* (`service.py`) | Se entregó la versión de antes de formatear | `docker compose run --rm tests ruff format .` |
| Al retomar en el Mac, faltaba openpyxl | La imagen de `tests` era de antes de la 1.1 | `docker compose build tests` cada vez que cambian las dependencias |
| `docker compose run` no recoge las dependencias nuevas | `run` solo construye la imagen si no existe | `docker compose build tests` (o `up -d --build` para la app) |

---

## 13. Chuleta de comandos

```bash
# --- Dependencias nuevas (pyproject.toml) → lock → imagen ---
docker run --rm -v "$PWD/backend:/app" -w /app python:3.12-slim \
  sh -c "pip install -q --root-user-action=ignore uv==0.11.32 && uv lock"   # Git Bash: MSYS_NO_PATHCONV=1 delante
docker compose build tests                 # tests con las dependencias nuevas
docker compose up -d --build               # la app con las dependencias nuevas

# --- Comprobaciones ---
docker compose run --rm tests                            # pytest (97)
docker compose run --rm tests pytest tests/test_transfers.py -q   # un solo archivo
docker compose run --rm tests ruff check .
docker compose run --rm tests ruff format .              # arregla el formato
docker compose run --rm web                              # lint + build del frontend

# --- Mirar lo importado en la BD de desarrollo ---
docker compose exec db psql -U caudal -d caudal -P pager=off \
  -c "SELECT a.name, t.date, t.description, t.amount, t.category_status, t.is_internal_transfer
      FROM transactions t JOIN accounts a ON a.id = t.account_id ORDER BY t.date DESC;"

# --- Probar la API a mano ---
# http://localhost:8080 (entrar) y, en la misma pestaña, http://localhost:8080/api/docs
```

---

## 14. Glosario

| Término | Qué es |
|---|---|
| **Huella** (`fingerprint`) | Resumen SHA-256 de lo que identifica un movimiento; si ya existe en la cuenta, no se vuelve a guardar |
| **`ON CONFLICT DO NOTHING`** | En un `INSERT`, saltarse sin error las filas que chocan con una restricción única |
| **`RETURNING`** | Que un `INSERT`/`UPDATE` devuelva columnas de las filas afectadas |
| **Transferencia interna** | Dinero que pasa entre cuentas del mismo usuario; no cuenta como gasto ni como ingreso |
| **Pista del extracto** (`transfer_hint`) | Dato del propio banco que indica de dónde viene el dinero (`imaginBank` en Wise) |
| **Saldo de referencia** | Último saldo conocido de una cuenta y su fecha; base del saldo calculado |
| **multipart/form-data** | Formato para enviar archivos y campos en una misma petición HTTP |
| **`Decimal`** | Número decimal exacto de Python; para el dinero, nunca `float` |
| **`quantize`** | Redondear o fijar un `Decimal` a un número concreto de decimales |
| **Zip bomb** | Archivo comprimido pequeño que ocupa muchísimo al descomprimirlo |
| **`FormData`** | Objeto del navegador para construir un envío multipart |
| **Drag and drop** | Arrastrar un archivo desde el escritorio y soltarlo en la página |
