# Fase 1c · Categorización + pestañas Movimientos y Patrimonio

> **Versión:** `0.3.0` · **Fechas:** 2026-10-21 → 2026-10-30 · **Estado:** ✅ terminada

El objetivo de la Fase 1c es que **Caudal ya sea útil en el día a día**: los movimientos importados se categorizan solos con reglas que aprenden de tus correcciones, y las pestañas **Movimientos** y **Patrimonio** enseñan los totales del mes y su evolución, como en la maqueta.

Este documento explica **qué se ha hecho**, **cómo** y **por qué**, con apuntes para aprender cada concepto. La fase se hizo en 5 partes, cada una probada y guardada con su commit, entre el Mac y el PC.

---

## Índice

1. [Resumen y estado](#1-resumen-y-estado)
2. [Cómo trabajamos en esta fase](#2-cómo-trabajamos-en-esta-fase)
3. [Archivos nuevos y cambiados](#3-archivos-nuevos-y-cambiados)
4. [Parte 1.1: motor de reglas y categorías iniciales](#4-parte-11-motor-de-reglas-y-categorías-iniciales)
5. [Parte 1.2: API de movimientos, categorías y reglas](#5-parte-12-api-de-movimientos-categorías-y-reglas)
6. [Parte 1.3: API de los paneles](#6-parte-13-api-de-los-paneles)
7. [Parte 1.4: pestañas, Movimientos, Revisar y Ajustes](#7-parte-14-pestañas-movimientos-revisar-y-ajustes)
8. [Parte 1.5: indicadores y gráficos](#8-parte-15-indicadores-y-gráficos)
9. [Cierre: criterios de "hecho"](#9-cierre-criterios-de-hecho)
10. [Decisiones de la fase](#10-decisiones-de-la-fase)
11. [Problemas encontrados y cómo se resolvieron](#11-problemas-encontrados-y-cómo-se-resolvieron)
12. [Chuleta de comandos](#12-chuleta-de-comandos)
13. [Glosario](#13-glosario)

---

## 1. Resumen y estado

| Parte | Qué | Commit | Estado |
|---|---|---|---|
| 1.1 | Motor de reglas, categorías y reglas iniciales, migración `0002` | `dec4a31` | ✅ |
| 1.2 | API de movimientos (listar, editar, borrar), categorías y reglas | `1c0386a` | ✅ |
| 1.3 | API de los paneles: patrimonio y flujo de caja | `f88de4b` | ✅ |
| 1.4 | 3 pestañas, tabla de Movimientos, Revisar, Ajustes, Inversiones vacía | `9e82c57` | ✅ |
| 1.5 | Indicadores y gráficos de Movimientos y Patrimonio | `feat: add kpis and charts…` | ✅ |
| Cierre | Criterios de "hecho", CHANGELOG `0.3.0`, README, DISENO y CLAUDE.md | `docs: close phase 1c` | ✅ |

**Tests:** 172 en total (75 nuevos en esta fase). ruff, ESLint, Prettier y el build, sin avisos. Las pantallas se probaron en Chromium con los ejemplos de `samples/`, sin errores en la consola.

---

## 2. Cómo trabajamos en esta fase

Igual que en la 1b: partes pequeñas con archivos completos (bloques `cat > … <<'EOF'`), comprobaciones (`wc -l`, pytest, ruff, `docker compose run --rm web`) y un commit por parte en `main`.

Novedades:
- **Una fase por conversación:** la 1c se hizo entera en el mismo chat, aunque con pausas de varios días. Al volver, se miraba el estado en GitHub (`git log`) en lugar de repetir el contexto.
- **Cambios pequeños con `git apply`:** para tocar pocas líneas de un archivo largo (`ImportPage.tsx`, `api.ts`…) se pegaba un parche con `git apply --ignore-whitespace <<'EOF' … EOF`. Si no encaja, no aplica nada a medias.
- **La 1.4 se entregó de una vez** (unos 20 archivos de frontend), ya probada en un navegador, en lugar de en tres trozos.

---

## 3. Archivos nuevos y cambiados

```text
backend/
├── alembic/versions/0002_rules_review_and_seed.py ← reglas sin categoría + semilla (1.1)
├── app/
│   ├── main.py                       ← registra categories, rules y dashboard
│   ├── categories/
│   │   ├── seed.py                   ← categorías y reglas iniciales           (1.1)
│   │   └── rules.py                  ← motor: palabra entera, prioridad        (1.1–1.2)
│   ├── dashboard/
│   │   ├── months.py                 ← meses «AAAA-MM»                         (1.3)
│   │   └── service.py                ← saldos, ingresos/gastos, por categoría  (1.3)
│   ├── api/
│   │   ├── setup.py                  ← crea la semilla al crear los usuarios   (1.1)
│   │   ├── imports.py                ← + categorized en el resumen             (1.1)
│   │   ├── transactions.py           ← GET con filtros, PATCH, DELETE          (1.2)
│   │   ├── categories.py             ← CRUD de categorías                      (1.2)
│   │   ├── rules.py                  ← CRUD de reglas + /apply                 (1.2)
│   │   └── dashboard.py              ← net-worth y cashflow                    (1.3)
│   ├── importers/service.py          ← aplica las reglas al importar           (1.1)
│   └── models/rule.py                ← category_id opcional                    (1.1)
└── tests/
    ├── conftest.py                   ← + fixture login (usuario con semilla)   (1.2)
    ├── test_categories.py            ← motor, semilla, migración (27)          (1.1)
    ├── test_categories_api.py        ← (12)                                    (1.2)
    ├── test_rules_api.py             ← «¿Aplicar siempre?», reaplicar (10)     (1.2)
    ├── test_transactions_api.py      ← filtros, edición, borrado (13)          (1.2)
    └── test_dashboard_api.py         ← totales contra sumas a mano (13)        (1.3)
frontend/src/
├── api.ts · format.ts · events.ts    ← llamadas nuevas, formatos, aviso de cambios
├── App.tsx · AppShell.tsx            ← rutas nuevas, pestañas, contador        (1.4)
├── hooks/                            ← useLookups, useDebounced, useDashboard  (1.4–1.5)
├── components/                       ← Modal, StatusBadge, CategorySelect, ApplyAlways,
│                                       TransactionDialog, Kpi, Charts, MovementsSummary
├── pages/MovementsPage.tsx           ← Movimientos                             (1.4–1.5)
├── pages/ReviewPage.tsx              ← Revisar                                 (1.4)
├── pages/SettingsPage.tsx            ← Ajustes → Categorías y reglas           (1.4)
├── pages/InvestmentsPage.tsx         ← Inversiones vacía                       (1.4)
├── pages/PanelPage.tsx               ← Patrimonio                              (1.5)
├── pages/ImportPage.tsx              ← botón Revisar, aviso de cambios         (1.4)
└── styles.css                        ← pestañas, tabla, ventana, gráficos      (1.4–1.5)
```

---

## 4. Parte 1.1: motor de reglas y categorías iniciales

### Qué se hizo

- **`categories/seed.py`:** 13 categorías de gasto, 5 de ingreso y 13 reglas iniciales, con prioridades: **10** Bizum (sin categoría), **50** las del usuario, **100** las iniciales. `seed_user_defaults()` no hace nada si el usuario ya tiene categorías.
- **`categories/rules.py`:**
  - `pattern_regex()` convierte el texto de la regla en una expresión regular de **palabra entera**.
  - `compile_rules()` las ordena (prioridad, texto más largo, más antigua) y `find_rule()` devuelve la primera que encaja.
  - `apply_rules()` categoriza lo que está **por revisar**; nunca toca lo manual ni las internas.
- **Migración `0002`:** `rules.category_id` pasa a admitir `NULL` y crea la semilla para los usuarios que ya existían. Lleva su propia copia de las listas.
- **Al importar**, primero se buscan las transferencias internas y después se aplican las reglas. El resumen añade `categorized`.
- **Al apuntar a mano**, también se aplican las reglas.

### Apuntes para aprender

- **Palabra entera con *lookarounds*:** `(?<![^\W_])BAR(?![^\W_])` significa «BAR, sin una letra o número justo antes ni justo después». `[^\W_]` es «letra o número de cualquier alfabeto». El borde solo se exige en los extremos que son letra o número: `*AMZ` no necesita nada antes del asterisco.
- **`re.escape()`:** el texto de la regla se trata como texto, no como expresión regular. Así, el punto de `WWW.AMAZ` no significa «cualquier carácter».
- **Normalizar antes de comparar:** `NFKD` separa la letra de su acento (`à` → `a` + `̀`) y después se quitan las marcas. Se normalizan tanto el concepto como la regla.
- **Una migración con datos:** `op.get_bind()` da la conexión de la migración. Con `sa.table(...)` se describen solo las columnas que hacen falta, sin importar los modelos de la app (que pueden cambiar más adelante).
- **El orden importa:** si las reglas se aplicaran antes que las transferencias, la salida a Wise (`enviament de dine`) podría quedar con una categoría de gasto.

---

## 5. Parte 1.2: API de movimientos, categorías y reglas

### Qué se hizo

- **`GET /api/transactions`:** `month`, `q` (concepto o nombre de categoría), `category`, `status` (`review`, `auto`, `manual`, `internal`), `account`, `limit` (hasta 1000; `0` = solo el total) y `offset`. Devuelve `{items, total}`, del más reciente al más antiguo.
- **`PATCH /api/transactions/{id}`:** cuenta, fecha, concepto, importe, `category_id` (con un id → `manual`; con `null` → por revisar y se le pasan las reglas) e `is_internal_transfer`.
- **`DELETE /api/transactions/{id}`.**
- **`/api/categories`:** listar (con cuántos movimientos y reglas tiene cada una), crear, editar y borrar. Borrar devuelve sus movimientos a «por revisar» y les pasa las demás reglas.
- **`/api/rules`:** listar en el orden del motor, `POST` que **crea o sustituye** la regla con el mismo texto, `PATCH` y `DELETE`.
- **`POST /api/rules/apply`:** reaplica a lo pendiente; con `include_auto=true`, también a lo automático (un `auto` que ya no encaja vuelve a «por revisar»).
- **Fixture `login`** en `conftest.py`: crea el usuario con su semilla e inicia sesión.
- Todos los endpoints con su **test de aislamiento** (404 al tocar lo de otro usuario).

### Apuntes para aprender

- **`model_dump(exclude_unset=True)`:** en un `PATCH` distingue «no lo envío» de «lo envío a `null`». Es lo que permite que `category_id: null` signifique «quitar la categoría».
- **El nombre de un campo puede tapar su tipo:** en una clase de Pydantic, `date: date | None = None` falla, porque Python primero asigna `date = None` y después evalúa `date | None`. Se resuelve con `import datetime as dt` y `date: dt.date | None`.
- **`ILIKE` con comodines escapados:** `%` y `_` son comodines en SQL. Si el usuario busca «%», se escapan (`\%`) para buscarlos como texto.
- **Contar sin traer las filas:** `select(func.count()).select_from(query.subquery())` cuenta lo que devolvería la consulta con los mismos filtros.
- **Crear o sustituir (*upsert*):** «¿Aplicar siempre a BAR?» cuando ya existe la regla BAR no debe crear otra igual con distinta categoría (el orden entre ellas sería arbitrario).

---

## 6. Parte 1.3: API de los paneles

### Qué se hizo

- **`dashboard/months.py`:** `parse_month`, `add_months`, `month_end`, `last_months`.
- **`dashboard/service.py`:**
  - **Saldo de una cuenta a la fecha D:** `referencia + S(D) − S(fecha de referencia)`, con `S(x)` la suma acumulada de sus movimientos hasta `x`. Sin referencia (cuentas a mano), `S(D)`.
  - **Ingresos y gastos por mes** sin internas, con una sola consulta agrupada por `to_char(fecha, 'YYYY-MM')`.
  - **Gasto por categoría** del mes, con «Sin categoría» para lo pendiente; suma exactamente el gasto del mes.
  - Tasa de ahorro y % de gasto respecto al mes anterior, redondeados al entero.
- **`GET /api/dashboard/net-worth`** y **`/cashflow`**, con `month` opcional (sin él, el mes del último movimiento).
- **Tests contra sumas hechas a mano** con los ejemplos: ingresos 152,00 €, gastos 107,32 €, ahorro 29 %, saldos 67,23 € y 147,45 €, y 50,00 € + 120,00 € a final de agosto.

### Apuntes para aprender

- **Calcular el saldo en vez de guardarlo:** guardar el saldo en cada movimiento obliga a recalcular todo al editar o borrar uno. Con el saldo de referencia del extracto y la suma de movimientos, siempre cuadra.
- **Suma acumulada + búsqueda binaria:** se suman los movimientos por día (`itertools.accumulate`) y `bisect_right` encuentra la posición de una fecha. Así, el saldo a 12 finales de mes no necesita 12 consultas.
- **`CASE WHEN` dentro de `SUM`:** `sum(case((amount > 0, amount)))` suma solo los positivos en la misma consulta que los negativos.
- **`ROUND_HALF_UP`:** el redondeo de toda la vida (29,5 → 30). Por defecto, `Decimal` redondea «al par» (29,5 → 30, pero 28,5 → 28).
- **`dataclass` + `asdict()`:** el servicio devuelve objetos de Python sin depender de FastAPI, y la API los convierte a sus modelos de Pydantic.

---

## 7. Parte 1.4: pestañas, Movimientos, Revisar y Ajustes

### Qué se hizo

- **`AppShell`:**
  - Barra lateral con Patrimonio, Movimientos (con el **contador de «por revisar»**), Inversiones y Ajustes.
  - Botón «Importar extracto» siempre visible.
  - Pestañas debajo del título, como en la maqueta.
- **Movimientos:**
  - tabla con buscador (con espera de 300 ms) y filtros por mes, categoría, estado y cuenta;
  - etiquetas Auto, Revisar, Manual e Interna;
  - «Ver más» de 100 en 100;
  - ventana (`<dialog>`) para añadir, editar y borrar. Borrar pide confirmación.
- **Revisar:**
  - lista de lo pendiente; al elegir la categoría aparece **«¿Aplicar siempre?»** con el texto propuesto, que se puede editar;
  - con los Bizum, no se ofrece;
  - «Es un traspaso entre mis cuentas».
- **Ajustes:**
  - categorías por tipo, con color, nombre, uso y borrar (con aviso de lo que pasará);
  - reglas en el orden del motor, con texto, categoría, origen (Inicial / Tuya), editar y borrar;
  - formularios de nueva categoría y nueva regla, y «Reaplicar a todo».
- **Inversiones:** estado vacío.
- **Rutas nuevas:** `/patrimonio`, `/movimientos`, `/movimientos/importar`, `/movimientos/revisar`, `/inversiones` y `/ajustes`, con redirecciones desde `/panel` e `/importar`.
- **`events.ts`:** un evento del navegador avisa de que han cambiado los datos, y el contador, las listas y los paneles se recargan solos.

### Apuntes para aprender

- **`<dialog>` + `showModal()`:** el navegador ya trae una ventana modal accesible: atrapa el foco, se cierra con Esc y deja inerte el resto de la página. No hace falta ninguna librería.
- **`StrictMode` monta dos veces en desarrollo:** si el efecto que abre el diálogo lo cerrara en la limpieza, en desarrollo se cerraría solo al abrirse. Por eso no se cierra en la limpieza: al desmontarse, el `<dialog>` sale del DOM y se cierra solo.
- **«Cargando» sin `setState` dentro del efecto:** se guarda junto a los datos la *clave* de los filtros con la que se pidieron (`loaded.key`). Si no coincide con la actual, está cargando. Así se evita un `setLoading(true)` dentro del `useEffect`, que la regla de ESLint de React marca.
- **Esperar a que el usuario deje de escribir (*debounce*):** `useDebounced` solo cambia el valor cuando lleva 300 ms sin cambiar. Así no se lanza una petición por cada tecla.
- **Un `.tsx` solo exporta componentes:** la recarga en caliente de Vite necesita que los `.tsx` solo exporten componentes. Por eso `appliedMessage` está en `applyAlwaysResult.ts`.
- **`key` que incluye los datos:** `<CategoryRow key={`${id}-${name}-${color}`}>` hace que la fila se reinicie si la categoría cambia desde fuera, sin copiar props al estado.
- **`type="month"` no funciona en Safari:** por eso el filtro de mes es un desplegable con los últimos 24 meses.

---

## 8. Parte 1.5: indicadores y gráficos

### Qué se hizo

- **Movimientos:**
  - 4 indicadores: dinero en cuentas, ingresos del mes, gastos del mes comparados con el mes anterior y tasa de ahorro;
  - ingresos vs gastos a 12 meses;
  - gasto por categoría en un donut con porcentajes.
- **Patrimonio:**
  - 4 indicadores: patrimonio neto, liquidez, inversiones (0 hasta la Fase 3) y ahorro del mes;
  - evolución a 12 meses en barras apiladas;
  - patrimonio por entidad;
  - reparto «Efectivo / Fondo monetario».
- **Componentes:** `Kpi`, `Charts` (`IncomeExpenseChart`, `NetWorthChart`, `Donut`, `EntityBars`) y `MovementsSummary`.
- **Hook `useDashboard`:** pide los datos y los vuelve a pedir cuando cambian.
- **Formatos nuevos:**
  - `formatEurRounded`: euros sin céntimos, para los indicadores, como en la maqueta;
  - `formatMonthShort`: «Sep»;
  - `monthName`: «agosto».

### Apuntes para aprender

- **Gráficos con CSS:** una barra es un `div` con `height` en píxeles proporcional al máximo. El donut es un `conic-gradient` con un tramo de color por porción y un círculo blanco encima. Para estos gráficos no hace falta una librería de 100 KB.
- **`role="img"` y `aria-label`:** un lector de pantalla lee el gráfico como una imagen con su descripción. El `title` de cada barra enseña los importes al pasar el ratón.
- **Los importes siguen siendo texto:** solo se pasan a `Number` para calcular alturas y porcentajes del dibujo. Las cifras que se leen salen tal cual de la API, calculadas con `Decimal`.
- **Funciones estables para los efectos:** `const loadCashflow = () => api.cashflow()` fuera del componente. Si estuviera dentro, sería una función nueva en cada render y el efecto se repetiría sin parar.

---

## 9. Cierre: criterios de "hecho"

| Criterio (CLAUDE.md, Fase 1c) | Cómo se comprobó | Resultado |
|---|---|---|
| Tras importar un mes real, todo lo que no sea Bizum queda categorizado | **Aplazado** a la revisión final con datos reales (DISENO §17, pendiente 11). Cómo hacerlo: importar un mes, pasar una vez por Revisar con «¿Aplicar siempre?» y comprobar que solo quedan Bizum. Con solo las 13 reglas iniciales **no** se cumple a la primera; se cumple a partir del segundo mes | ⏸️ aplazado |
| Los totales del panel coinciden con una suma manual | `test_dashboard_api.py` compara con sumas hechas a mano (152,00 € / 107,32 € / 29 %; saldos 67,23 € y 147,45 €). En la pantalla, los indicadores dan 215 € · 152 € · 107 € · 29 % | ✅ |
| Se parece a la maqueta | Pestañas, barra lateral, indicadores, ingresos vs gastos, donut, evolución, por entidad y reparto, con los colores y tipografías de la sección 14 de DISENO. Faltan presupuestos, avisos, recurrentes, objetivo y selector de mes (Fase 2) | ✅ |
| Los tests pasan | `docker compose run --rm tests` → **172 passed**; ruff, ESLint, Prettier y build sin avisos | ✅ |
| Tests de reglas, reaplicación y totales que excluyen las internas | `test_categories.py`, `test_rules_api.py`, `test_dashboard_api.py::test_internal_transfers_do_not_count` | ✅ |

---

## 10. Decisiones de la fase

Todas están ya pasadas a DISENO, CLAUDE.md, README o CHANGELOG.

| Decisión | Motivo | Dónde está |
|---|---|---|
| Categorías iniciales sin cambios | Confirmadas por Gerard | DISENO §9.4, §17 |
| Reglas por **palabra entera** | «contiene BAR» encajaba con BARCELONA o EMBARQUE | DISENO §9.4 |
| Bizum = regla **sin categoría** con prioridad 10 | Un Bizum puede ser cualquier cosa; «BIZUM ENVIAT BAR PEPE» no debe ir a Comida fuera | DISENO §9.4 |
| Prioridades 10 / 50 / 100 | Lo que el usuario enseña gana a lo inicial | DISENO §9.4 |
| `POST /api/rules` crea o sustituye | No tener dos reglas con el mismo texto y distinta categoría | CLAUDE.md §6 |
| «Reaplicar a todo» con `include_auto` | Corregir lo que categorizó mal una regla ya arreglada, sin tocar lo manual | DISENO §9.4 |
| Ajustes → Categorías y reglas en la 1c (no en la 4) | Sin pantalla, una regla mal creada solo se arreglaba desde `/api/docs` | DISENO §10 |
| Gráficos en CSS, sin Recharts | Igual que la maqueta y sin dependencias; Recharts solo si hace falta en la Fase 3 | DISENO §2 y §10, CLAUDE.md §3 |
| Devolución = ingreso | DISENO 9.1 decide por el signo; así el donut suma el gasto del mes | DISENO §9.1 |
| Mes de los paneles = el del último movimiento | Importar septiembre en octubre no debe dar un panel vacío | DISENO §10 |
| Saldo a una fecha = referencia + S(D) − S(R) | Funciona hacia delante y hacia atrás, sin guardar saldos | DISENO §10 |
| Rutas en castellano bajo `/movimientos/...` | URLs legibles; las antiguas redirigen | DISENO §10 |
| La 1.4 entera en un commit | Gerard prefirió ir rápido; se entregó ya probada en el navegador | Esta carpeta |
| Comprobaciones con datos reales, al final | Primero hacerlo todo funcional y después probar y retocar lo que no guste, de una vez | CLAUDE.md §4, DISENO §17 (pendiente 11) |

---

## 11. Problemas encontrados y cómo se resolvieron

| Problema | Causa | Solución |
|---|---|---|
| `TypeError: unsupported operand type(s) for \|: 'NoneType' and 'NoneType'` al importar la app | En `TransactionUpdate`, el campo `date` tapaba el tipo `date` | `import datetime as dt` y `date: dt.date \| None = None` |
| El eje de los gráficos decía «Sept» | `Intl` en `es-ES` abrevia septiembre como «sept.» | `formatMonthShort` se queda con las tres primeras letras |
| Las filas de reglas en Ajustes ocupaban dos líneas | Demasiados elementos en un `flex` con `wrap` | Rejilla (`.rule-row`) de 4 columnas; en el móvil, una |
| La 1.5 funcionaba pero no estaba en GitHub | Se dejó el trabajo después de probar, sin commit o sin push | `git status` y `git log --oneline -3`; comparar con `git log -1 origin/main` antes de cambiar de equipo |
| En la tabla del móvil hay que desplazarse en horizontal | 6 columnas no caben en 390 px | Se deja así; la usabilidad en el móvil es de la Fase 4 |

---

## 12. Chuleta de comandos

```bash
# --- Comprobaciones ---
docker compose run --rm tests                                   # pytest (172)
docker compose run --rm tests pytest tests/test_dashboard_api.py -q
docker compose run --rm tests ruff check .
docker compose run --rm tests ruff format --check .
docker compose run --rm web                                     # lint + build del frontend
docker compose run --rm web sh -c "npm run format"              # arregla el formato del frontend

# --- ¿Está todo subido? ---
git status                         # "nothing to commit"
git log --oneline -1               # mi último commit…
git log --oneline -1 origin/main   # …tiene que coincidir con el de GitHub (después de git fetch)

# --- Mirar categorías y reglas en la BD de desarrollo ---
docker compose exec db psql -U caudal -d caudal -P pager=off \
  -c "SELECT u.username, count(DISTINCT c.id) AS categorias, count(DISTINCT r.id) AS reglas
      FROM users u LEFT JOIN categories c ON c.user_id = u.id
      LEFT JOIN rules r ON r.user_id = u.id GROUP BY u.username;"

# --- Probar la API a mano ---
# http://localhost:8080 (entrar) y, en la misma pestaña, http://localhost:8080/api/docs
#   GET /api/dashboard/cashflow · GET /api/transactions?status=review&limit=0
```

---

## 13. Glosario

| Término | Qué es |
|---|---|
| **Regla** | «Si el concepto contiene la palabra X → categoría Y». Sin categoría, deja el movimiento por revisar |
| **Prioridad** | Orden en que se miran las reglas: el número más bajo primero; gana la primera que encaja |
| **Semilla** (*seed*) | Datos iniciales que se crean al dar de alta un usuario: categorías y reglas |
| **`category_status`** | `auto` (por una regla), `manual` (puesta a mano) o `review` (por revisar) |
| ***Lookaround*** | Parte de una expresión regular que mira lo que hay antes (`(?<!…)`) o después (`(?!…)`) sin consumirlo |
| ***Upsert*** | Crear si no existe o sustituir si ya existe |
| **`exclude_unset`** | Opción de Pydantic para quedarse solo con los campos que se han enviado |
| **Suma acumulada** | Lista en la que cada posición es la suma de todas las anteriores |
| **`bisect_right`** | Búsqueda binaria: en qué posición de una lista ordenada iría un valor |
| **`conic-gradient`** | Degradado de CSS que gira alrededor de un punto; con tramos de color duros, un gráfico de tarta |
| **`<dialog>`** | Elemento HTML para ventanas; con `showModal()`, modal y accesible |
| ***Debounce*** | Esperar a que algo deje de cambiar un rato antes de reaccionar |
| **KPI** | Indicador clave: una cifra resumen (gastos del mes, tasa de ahorro…) |
