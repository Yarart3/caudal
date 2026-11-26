# Fase 5 · Extras (parte adelantada)

> **Versión:** `0.8.0` al cerrar la fase entera · **Fechas:** 2026-11-26 · **Estado:** ⏳ parte adelantada terminada (5.1 a 5.5); el resto, después de la Fase 4

Gerard decidió (2026-11-26) adelantar a la Fase 4 los extras que **no dependen de los padres**, mientras él hace la R.4 y la R.5 con sus datos reales. Eligió: notas y etiquetas, deshacer importación, exportar, tema oscuro y «solo largo plazo». Quedan para después de la Fase 4: previsión del gasto, ganancias realizadas por año, sugerencias con un modelo local (Ollama) y multidivisa en Wise (necesita un extracto de ejemplo en otra divisa).

---

## Índice

1. [Resumen y estado](#1-resumen-y-estado)
2. [Decisiones de la fase](#2-decisiones-de-la-fase)
3. [Archivos nuevos y cambiados](#3-archivos-nuevos-y-cambiados)
4. [Cómo se probó](#4-cómo-se-probó)
5. [Problemas encontrados y cómo se resolvieron](#5-problemas-encontrados-y-cómo-se-resolvieron)
6. [Criterios de "hecho"](#6-criterios-de-hecho)
7. [Apuntes para aprender](#7-apuntes-para-aprender)
8. [Chuleta de comandos y glosario](#8-chuleta-de-comandos-y-glosario)

---

## 1. Resumen y estado

| Parte | Qué | Commit | Estado |
|---|---|---|---|
| — | Documentación alineada con la Fase R y plan de la Fase 5 | `docs: align design doc with phase R and plan early phase 5 extras (phase R)` | ✅ |
| 5.1 | Notas y etiquetas en los movimientos (migración `0009`) | `add notes and tags to transactions (phase 5, step 5.1)` | ✅ |
| 5.2 | Historial de importaciones y deshacer (migración `0010`) | `add import history and undo import (phase 5, step 5.2)` | ✅ |
| 5.3 | Exportar a Excel e «Imprimir / PDF» | `add excel export of transactions and print styles (phase 5, step 5.3)` | ✅ |
| 5.4 | Tema oscuro y Ajustes → Apariencia | `add dark theme with appearance setting (phase 5, step 5.4)` | ✅ |
| 5.5 | «Solo largo plazo» en Inversiones | `add long-term only filter to investments (phase 5, step 5.5)` | ✅ |
| 5.6 | Cierre de la parte adelantada: documentación | `docs: close early part of phase 5` | ✅ |

**Tests:** 723 en total (30 nuevos). ruff, ESLint, Prettier y el build, sin avisos. Pantallas revisadas en Chromium, en claro, en oscuro y en la vista de impresión.

---

## 2. Decisiones de la fase

### Notas y etiquetas (5.1)
- **Etiquetas como lista dentro del movimiento** (`ARRAY(String(30))` con índice GIN) y no con dos tablas (`tags` + `transaction_tags`). Para etiquetar, filtrar y contar basta; renombrar una etiqueta en todos los movimientos sería más fácil con tablas, pero no hace falta todavía.
- **Limpieza al guardar:** se quitan los espacios de más y las repetidas sin mirar mayúsculas, y si ya usas «Viaje», escribir «VIAJE» guarda «Viaje». Máximo 10 por movimiento y 30 caracteres cada una.
- El buscador (`q`) mira también en la nota.

### Deshacer importación (5.2)
- Se registran solo las importaciones que traen algo nuevo. **No se guarda el nombre del archivo**: el de Wise lleva el número del extracto (DISENO 8.3, mínimo de datos).
- **Saldo de referencia:** se guarda el de antes y el que puso la importación; al deshacer vuelve al de antes **solo si nadie lo ha cambiado después**.
- **Transferencias internas:** las parejas no se guardan (DISENO 9.3), así que la otra pata se busca como al emparejar. Si es ambiguo, se deja marcada: es mejor una interna de más que esconder una de verdad.
- **No** se deshacen las importaciones del historial de inversiones: podrían dejar ventas sin sus compras. Esas operaciones se borran una a una (se comprueba que no se vende más de lo que hay).

### Exportar (5.3)
- **Excel con openpyxl**, que ya se usaba para leer extractos: sin dependencias nuevas. Mismos filtros que la lista, sin límite de filas, y una hoja «Resumen» con los totales **sin internas** (como los paneles).
- **Importes como número** con formato de euros, para poder sumar en Excel; fechas como fecha de Excel.
- **PDF con el navegador** («Imprimir / PDF» → «Guardar como PDF») en lugar de generarlo en el servidor: sin librerías nuevas y sale igual que la pantalla.

### Tema oscuro (5.4)
- Todos los colores de los componentes pasan a ser **variables CSS** con nombre (`--good`, `--warn`, `--info`, `--field`…). Quedan fijos a propósito la barra lateral (oscura en los dos temas), los colores de las series de los gráficos y los avatares.
- **«Automático» por defecto** (sigue al sistema). La elección se guarda en el **navegador** (`localStorage`), no en la BD: es una preferencia del equipo y no tiene que viajar en los backups.
- **Al imprimir, siempre claro**, para no gastar tinta ni sacar un PDF negro.

### Solo largo plazo (5.5)
- Se filtra en `build()`, la raíz de la cartera: así **todo** (FIFO, TIR, aportaciones, comisiones, comparativa) sale de las mismas operaciones. Las listas de Operaciones y Productos no se filtran: son el registro para apuntar y editar.

---

## 3. Archivos nuevos y cambiados

| Archivo | Qué |
|---|---|
| `backend/alembic/versions/0009_transaction_notes_tags.py` | `transactions.note`, `transactions.tags` + índice GIN |
| `backend/alembic/versions/0010_imports.py` | Tabla `imports` y `transactions.import_id` |
| `backend/app/models/import_batch.py` | Modelo `Import` |
| `backend/app/importers/undo.py` | Deshacer una importación |
| `backend/app/exports/__init__.py` | Excel de movimientos (hojas «Movimientos» y «Resumen») |
| `backend/app/api/transactions.py` | Nota, etiquetas, `/tags`, filtros comunes y `/export` |
| `backend/app/api/imports.py` | `GET /api/imports`, `DELETE /api/imports/{id}` e `import_id` |
| `backend/app/importers/service.py` | Registra cada importación |
| `backend/app/investments/portfolio.py` · `backend/app/api/portfolio.py` | `long_term_only` / `?long_term=true` |
| `backend/tests/test_transaction_notes_tags.py` · `test_import_undo.py` · `test_transactions_export.py` · `test_long_term_filter.py` | Tests nuevos |
| `frontend/src/theme.ts` · `components/AppearanceCard.tsx` · `components/ImportHistoryCard.tsx` | Tema, Apariencia e historial de importaciones |
| `frontend/src/styles.css` | Variables, tema oscuro, etiquetas e impresión |
| `frontend/src/components/TransactionDialog.tsx` · `pages/MovementsPage.tsx` · `pages/InvestmentsPage.tsx` · `AppShell.tsx` | Pantallas |

---

## 4. Cómo se probó

- Todo en Docker, en un entorno **aislado** (red, BD e imágenes `caudal-claude-*`), sin tocar las instancias real y de desarrollo.
- Pantallas: la app con los ejemplos inventados de `samples/` y una cartera inventada, y capturas con **Playwright** (Chromium sin ventana) en claro, en oscuro y con `emulate_media(media="print")`. Sin errores en la consola.

---

## 5. Problemas encontrados y cómo se resolvieron

| Problema | Causa | Solución |
|---|---|---|
| Dos tests de sincronización fallarían con cada migración nueva | Tenían escrito `"0008"` como última migración | Comparan con `head_revision()` / la mayor de las conocidas |
| Un texto que empieza por «=» saldría como fórmula en el Excel | openpyxl toma por fórmula cualquier `str` que empiece por `=` | Cada texto se marca como texto (`cell.data_type = "s"`), con test |
| En oscuro, la barra lateral se habría vuelto clara | `.side` usaba `--ink`, que en oscuro es el color claro del texto | Variable propia, `--side` |
| El PDF saldría negro con el tema oscuro | La impresión usa los colores de la pantalla | `beforeprint` / `afterprint` fuerzan el tema claro |
| Los gráficos saldrían vacíos en el PDF | Los navegadores no imprimen fondos de CSS | `print-color-adjust: exact` |

---

## 6. Criterios de "hecho"

| Criterio (CLAUDE.md §7, Fase 5: «lo elegido funciona, con tests») | Estado |
|---|---|
| Notas y etiquetas: alta, edición, filtro, búsqueda, aislamiento | ✅ 10 tests |
| Deshacer importación: borra, saldo, transferencias, ambigüedad, aislamiento | ✅ 9 tests |
| Exportar: columnas, filtros, totales, sin fórmulas, aislamiento | ✅ 7 tests; PDF revisado en Chromium |
| Tema oscuro: legible en todas las pestañas, impresión en claro | ✅ revisado con capturas |
| Solo largo plazo: cálculos, API, comparativa, aislamiento | ✅ 4 tests y captura |
| Probarlo Gerard en su instancia de desarrollo | ⏳ |

---

## 7. Apuntes para aprender

- **Arrays en PostgreSQL + índice GIN.** Una columna puede guardar una lista (`VARCHAR(30)[]`). `tags @> ARRAY['viaje']` («contiene») usa el índice GIN, que indexa cada elemento por separado: es el mismo tipo de índice que se usa para búsqueda de texto y JSON. `unnest(tags)` convierte la lista en filas para contarlas con `GROUP BY`.
- **Inyección de fórmulas (CSV/Excel injection).** Si una celda empieza por `=`, `+`, `-` o `@`, Excel puede ejecutarla como fórmula (por ejemplo, un `HYPERLINK` a una web). En `.xlsx` basta con guardar la celda como texto; en un CSV haría falta anteponer una comilla.
- **Variables CSS y `prefers-color-scheme`.** `:root { --card: #fff }` y luego `var(--card)`. Para el tema oscuro solo se redefinen las variables: dentro de `@media (prefers-color-scheme: dark)` (automático) o con `:root[data-theme='dark']` (elegido). `color-scheme: dark` hace que el navegador pinte en oscuro también los controles nativos (selects, barras de desplazamiento).
- **`@media print`.** Estilos que solo se aplican al imprimir: ocultar la navegación, evitar que una tarjeta se parta entre páginas (`break-inside: avoid`) y forzar los fondos (`print-color-adjust: exact`).
- **Dependencias de FastAPI como filtros.** `filters: Annotated[Filters, Depends(transaction_filters)]` lee los parámetros de la URL una sola vez y los comparten la lista y la exportación.

---

## 8. Chuleta de comandos y glosario

| Para qué | Comando |
|---|---|
| Ver las etiquetas de la base (desarrollo) | `docker compose exec db psql -U caudal -d caudal -P pager=off -c "SELECT unnest(tags), count(*) FROM transactions GROUP BY 1"` |
| Ver las importaciones registradas | `docker compose exec db psql -U caudal -d caudal -P pager=off -c "SELECT id, account_id, first_date, last_date, new_count FROM imports ORDER BY id DESC"` |

**Glosario:** *GIN* (Generalized Inverted Index, índice para listas, JSON y texto) · *`localStorage`* (almacén del navegador por web, que no sale del equipo) · *Playwright* (herramienta para manejar un navegador desde código y sacar capturas).
