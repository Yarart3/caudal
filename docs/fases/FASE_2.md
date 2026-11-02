# Fase 2 · Control del gasto

> **Versión:** `0.5.0` · **Fechas:** 2026-10-31 a 2026-11-02 · **Estado:** ✅ terminada (con el criterio de «datos reales» aplazado a la revisión final)

El objetivo de la Fase 2 es **saber si te estás pasando**. Caudal compara lo que gastas con lo que quieres gastar (presupuestos), te avisa cuando algo se desvía, detecta los pagos que se repiten y te enseña cuánto te falta para tu objetivo de patrimonio. Además, las dos pestañas tienen **selector de mes**.

Este documento explica **qué se ha hecho**, **cómo** y **por qué**, con apuntes para aprender cada concepto. La fase se hizo en 7 partes (2.1 a 2.7).

---

## Índice

1. [Resumen y estado](#1-resumen-y-estado)
2. [Decisiones de la fase](#2-decisiones-de-la-fase)
3. [Archivos nuevos y cambiados](#3-archivos-nuevos-y-cambiados)
4. [Parte 2.1: esquema de presupuestos y objetivo](#4-parte-21-esquema-de-presupuestos-y-objetivo)
5. [Parte 2.2: API de presupuestos](#5-parte-22-api-de-presupuestos)
6. [Parte 2.3: pagos recurrentes](#6-parte-23-pagos-recurrentes)
7. [Parte 2.4: avisos](#7-parte-24-avisos)
8. [Parte 2.5: objetivo de patrimonio](#8-parte-25-objetivo-de-patrimonio)
9. [Partes 2.6a y 2.6b: pantallas](#9-partes-26a-y-26b-pantallas)
10. [Cierre: criterios de "hecho"](#10-cierre-criterios-de-hecho)
11. [Problemas encontrados y cómo se resolvieron](#11-problemas-encontrados-y-cómo-se-resolvieron)
12. [Chuleta de comandos y glosario](#12-chuleta-de-comandos-y-glosario)

---

## 1. Resumen y estado

| Parte | Qué | Commit | Estado |
|---|---|---|---|
| 2.1 | Migración `0003`: `categories.monthly_budget` y tabla `goals` | `add monthly budgets and net worth goal schema` | ✅ |
| 2.2 | `GET/PUT /api/budgets` y estado OK / Al límite / Superado | `add monthly budgets api` | ✅ |
| 2.3 | Detección de pagos recurrentes y `GET /api/recurring` | `add recurring payments detection` | ✅ |
| 2.4 | Avisos del mes y `GET /api/alerts` (y arreglo de recurrentes) | `add monthly alerts and fix recurring with very different amounts` | ✅ |
| 2.5 | Objetivo de patrimonio: `GET/PUT/DELETE /api/goals` con hitos | `add net worth goal api with milestones` | ✅ |
| 2.6a | Indicadores y gráficos de Patrimonio y Movimientos (faltaban de la 1c) | `add kpis and charts to movements and net worth tabs` | ✅ |
| 2.6b | Selector de mes, presupuestos, avisos, recurrentes y objetivo en pantalla | `add month selector, budgets, alerts, recurring and goal cards` | ✅ |
| 2.7 | Cierre: documentación | `docs: close phase 2` | ✅ |

**Tests:** 327 en total (96 nuevos). ruff, ESLint, Prettier y el build, sin avisos.

---

## 2. Decisiones de la fase

- **Presupuestos y objetivo se ponen en la app**, no por chat. Cada usuario ve y cambia solo los suyos.
- **Presupuesto fijo por categoría de gasto** (el mismo cada mes). Estado: **OK** por debajo del 90 %, **Al límite** del 90 % al 100 %, **Superado** por encima del 100 %. Las categorías de ingreso no tienen presupuesto: si una categoría pasa a ingreso, su presupuesto se borra.
- **Un objetivo por usuario**, con hitos calculados: 1.000, 2.500, 5.000, 10.000, 25.000, 50.000, 100.000, 250.000, 500.000 y 1.000.000 €. Se enseñan los 3 siguientes. El porcentaje se redondea hacia abajo.
- **Recurrentes y avisos se calculan al pedirlos**, no se guardan en tablas. Así nunca quedan desfasados si se edita o borra un movimiento.
- **Selector de mes en la URL** (`?mes=2026-09`): se puede recargar o compartir. Sin parámetro, el mes del último movimiento.
- **Detección de recurrentes:**
  - Se agrupa por concepto normalizado (mayúsculas, sin acentos, sin palabras con números).
  - Importe dentro de ±10 % de la mediana y un solo pago por día.
  - Cadena mensual: huecos de 25 a 35 días, al menos 3 pagos y último pago de hace ≤ 62 días.
  - Cadena anual: huecos de 350 a 380 días, al menos 2 pagos y último pago de hace ≤ 400 días.
  - Se excluyen las transferencias internas y los conceptos con una regla sin categoría (Bizum).
- **Avisos** (en este orden): presupuesto superado (rojo), gasto alto (ámbar), cambio del gasto frente al mes anterior, recurrente nuevo y total de recurrentes (azul). «Gasto alto» = más de 1,5 veces la media de los hasta 3 meses anteriores con datos y al menos 30 € más; no se repite si la categoría ya superó su presupuesto.
- **Gráficos en CSS** (como en la 1c), sin librerías.

---

## 3. Archivos nuevos y cambiados

```text
backend/
├── alembic/versions/0003_budgets_and_goals.py
└── app/
    ├── models/{category.py, goal.py}      ← monthly_budget · Goal
    ├── budgets/service.py                 ← estado y gastos por categoría
    ├── recurring/service.py               ← detección
    ├── alerts/service.py                  ← avisos
    ├── goals/service.py                   ← porcentaje e hitos
    └── api/{budgets,recurring,alerts,goals}.py
frontend/src/
├── hooks/{useDashboard.ts, useMonthParam.ts}
├── components/{Kpi, Charts, MonthSelect, BudgetsCard, AlertsCard, RecurringCard, GoalCard}.tsx
└── pages/{MovementsPage, PanelPage}.tsx
```

---

## 4. Parte 2.1: esquema de presupuestos y objetivo

### Qué se hizo
- `categories.monthly_budget NUMERIC(12,2)` (opcional) con un `CHECK` que obliga a que sea mayor que 0.
- Tabla `goals`: un registro por usuario (`user_id` único, con borrado en cascada), nombre y meta mayor que 0.

### Apuntes para aprender
- **`CHECK` en la base de datos:** aunque la API valide, la base de datos es la última barrera. Un presupuesto negativo no puede entrar por ningún camino.
- **`UNIQUE` en `user_id`:** la base de datos garantiza «un objetivo por usuario», no solo el código.

---

## 5. Parte 2.2: API de presupuestos

### Qué se hizo
- `GET /api/budgets?month=` devuelve todas las categorías de gasto, con las que tienen presupuesto primero (las más consumidas arriba), lo gastado, lo que queda, el porcentaje y el estado.
- `PUT /api/budgets` pone o quita (`amount: null`) el presupuesto de varias categorías a la vez. O se guardan todas o ninguna.
- Errores en castellano: 404 si la categoría no existe o es de otro usuario, 422 si es de ingreso o aparece repetida.

### Apuntes para aprender
- **`Decimal` y `quantize`:** `60` se guarda como `60.00`, igual que lo devuelve la base de datos. Así el `PUT` y el `GET` dan el mismo texto.

---

## 6. Parte 2.3: pagos recurrentes

### Qué se hizo
- `detect_recurring` agrupa los movimientos por concepto, busca cadenas mensuales o anuales y calcula el importe, el total al mes, el próximo pago y si es nuevo en el mes elegido.

### Apuntes para aprender
- **Mediana frente a media:** un pago raro (una devolución, un cargo doble) no desplaza la mediana, así que el ±10 % no se rompe.
- **«Es nuevo»:** un recurrente es nuevo si la fecha en que se pudo detectar por primera vez cae en el mes elegido.

---

## 7. Parte 2.4: avisos

### Qué se hizo
- `monthly_alerts` junta los cinco tipos de aviso, cada uno con su nivel (`danger`, `warning`, `positive`, `info`) y su frase ya formateada en castellano.

### Apuntes para aprender
- **Umbral doble:** «1,5 veces la media» sola daría falsas alarmas en categorías pequeñas (de 2 € a 4 €). Por eso también se exige una diferencia mínima de 30 €.

---

## 8. Parte 2.5: objetivo de patrimonio

### Qué se hizo
- `GET /api/goals` devuelve el objetivo (o `null`), el patrimonio del mes, el porcentaje, lo que falta y los hitos alcanzados y siguientes.
- `PUT /api/goals` crea o cambia el objetivo. `DELETE /api/goals` lo quita (204, también si no había).

---

## 9. Partes 2.6a y 2.6b: pantallas

### Qué se hizo
- **2.6a:** el repositorio no tenía los indicadores y gráficos de la 1c (parte 1.5) aunque la documentación los daba por hechos. Se rehicieron: 4 indicadores, ingresos vs gastos a 12 meses, gasto por categoría, evolución del patrimonio, patrimonio por entidad y reparto por tipo.
- **2.6b:** selector de mes con flechas, tarjetas «Presupuestos del mes» (con ventana para editarlos), «Avisos» y «Pagos recurrentes» en Movimientos, y «Objetivo de patrimonio» (poner, editar y quitar) en Patrimonio.
- Comprobado en un navegador real, a 1400 px y a 390 px, con datos inventados.

### Apuntes para aprender
- **`useSearchParams`:** guarda el estado en la URL en lugar de en memoria; el mes elegido sobrevive a recargar la página.
- **Hook con función estable:** `useDashboard` recibe la función de carga definida fuera del componente; si fuera nueva en cada render, el efecto se repetiría sin parar.

---

## 10. Cierre: criterios de "hecho"

- ✅ Presupuestos, avisos, recurrentes, selector de mes y objetivo con hitos.
- ✅ Tests de recurrentes y avisos; aislamiento entre usuarios en cada endpoint nuevo.
- ✅ 327 tests, ruff, ESLint, Prettier y build sin avisos.
- ⏳ **Aplazado (DISENO §17, pendiente 11):** «Movimientos y Patrimonio se parecen a la maqueta con datos reales». Con datos inventados ya se parecen; falta comprobarlo con extractos reales. Al revisarlo, mirar con atención:
  - Que los **Bizum** no salgan como recurrentes.
  - Que los **umbrales de los avisos** (1,5× y 30 €) no avisen de más ni de menos.
  - Que la **ventana de recurrentes** (62 días) no oculte los de un mes aún sin importar.

---

## 11. Problemas encontrados y cómo se resolvieron

| Problema | Causa | Solución |
|---|---|---|
| Un presupuesto de una categoría que pasaba a ingreso hacía saltar el `CHECK` y la API decía «ya tienes una categoría con ese nombre» | No se limpiaba `monthly_budget` al cambiar a ingreso | Se pone a `NULL` antes de guardar |
| `PUT` devolvía `60` y `GET` `60.00` | Sin redondeo a céntimos | `quantize(0.01)` |
| Los recurrentes desaparecían si el mes elegido aún no estaba importado | Ventana de actividad de 45 días | Subida a 62 días |
| Error 500 en avisos cuando ningún pago estaba cerca de la mediana (±10 %) | Lista vacía en `_chain` | `if not cluster: return None` y test nuevo |
| Faltaban indicadores y gráficos de la 1c | La parte 1.5 nunca llegó al repositorio | Rehecha como 2.6a |
| Importe pegado al texto en «Pagos recurrentes» | Faltaba la clase `.list-row` | Añadida al CSS |

**Pendiente de otra fase:** en móvil (390 px), Movimientos se desborda a lo ancho por la tabla y Patrimonio unos píxeles por la barra lateral. Ya estaba antes de la Fase 2; se arregla en el repaso de usabilidad de la Fase 4.

---

## 12. Chuleta de comandos y glosario

```bash
docker compose run --rm tests                  # todos los tests
docker compose run --rm tests ruff check .     # lint del backend
docker compose run --rm tests ruff format .    # formatear el backend
docker compose run --rm web sh -c "npm ci --no-audit --no-fund && npx prettier --write src && npm run lint && npm run build"
docker compose up -d --build                   # reconstruir y arrancar
```

- **Presupuesto:** cantidad máxima que quieres gastar al mes en una categoría.
- **Hito:** cifra redonda de patrimonio (2.500 €, 5.000 €…) que sirve de meta intermedia.
- **Recurrente:** pago que se repite con el mismo concepto, un importe parecido y una periodicidad regular.
- **Mediana:** valor central de una lista ordenada; no le afectan los extremos.
