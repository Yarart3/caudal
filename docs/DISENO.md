# Caudal: documento de diseño

> **Fuente de verdad de las decisiones del proyecto** (qué se hace y por qué). La presentación general está en `README.md` y la forma de trabajar de Claude, fase a fase, en `CLAUDE.md`. Si una decisión cambia, se actualiza aquí.

- **Nombre de la app:** **Caudal** (el dinero que fluye y, a la vez, el patrimonio que se acumula)
- **Autor:** Gerard
- **Estado:** diseño cerrado, sin código todavía (empieza en la Fase 0)
- **Maqueta visual (referencia oficial del diseño):**
  - `maqueta/caudal-maqueta.html`: se abre con doble clic en el navegador, sin depender de Claude.
  - Versión editable en Claude Design: https://claude.ai/artifact/DXDvWvm4wy3PE4RYRtcckQ (privada, solo la ve Gerard; para usarla como app, pulsar ▶ Play).
- **Cómo trabaja Claude cada fase:** `CLAUDE.md` · **Cómo montar el proyecto en Claude:** `INSTRUCCIONES_PROYECTO_CLAUDE.md`.

---

## Índice

1. [Objetivo](#1-objetivo)
2. [Resumen de decisiones](#2-resumen-de-decisiones)
3. [Las tres pestañas](#3-las-tres-pestañas)
4. [Usuarios, inicio de sesión y privacidad entre usuarios](#4-usuarios-inicio-de-sesión-y-privacidad-entre-usuarios)
5. [Cuentas, bancos y brokers](#5-cuentas-bancos-y-brokers)
6. [Formatos de los extractos bancarios](#6-formatos-de-los-extractos-bancarios)
7. [Inversiones](#7-inversiones)
8. [Qué se guarda (modelo de datos)](#8-qué-se-guarda-modelo-de-datos)
9. [Lógica automática](#9-lógica-automática)
10. [Arquitectura y stack](#10-arquitectura-y-stack)
11. [Arranque y parada (Docker solo cuando quieras)](#11-arranque-y-parada-docker-solo-cuando-quieras)
12. [Copias de seguridad (pendrive + OneDrive)](#12-copias-de-seguridad-pendrive--onedrive)
13. [Seguridad y privacidad](#13-seguridad-y-privacidad)
14. [La maqueta](#14-la-maqueta)
15. [Roadmap por fases](#15-roadmap-por-fases)
16. [Paso a Mac](#16-paso-a-mac)
17. [Pendientes y decisiones abiertas](#17-pendientes-y-decisiones-abiertas)
18. [Referencias](#18-referencias)
19. [Instrucciones para Claude en este proyecto](#19-instrucciones-para-claude-en-este-proyecto)

---

## 1. Objetivo

Una aplicación **útil de verdad** para controlar **todo el dinero** de Gerard y de sus padres en un solo sitio:

- **Patrimonio:** cuánto se tiene en total (cuentas + inversiones) y cómo evoluciona.
- **Movimientos:** en qué se gasta y qué entra cada mes, **importando los extractos** del banco en lugar de introducir todo a mano. La app detecta sola si cada movimiento es un gasto o un ingreso y lo **categoriza**.
- **Inversiones:** la cartera de Trade Republic y Scalable Capital, con **precios actualizados automáticamente**, plusvalías, rentabilidad y comparativa con un indexado.

Funciona **en el PC de casa**, sin publicar nada en internet y sin coste mensual.

**De momento no es un proyecto para el CV.** Si más adelante se quiere enseñar, se hará una versión demo aparte con datos inventados (Fase 7).

---

## 2. Resumen de decisiones

| Tema | Decisión |
|---|---|
| Nombre | **Caudal** |
| Dónde funciona | PC de casa de Gerard (Windows ahora, Mac en ~1 mes). Nada en la nube ni en un servidor. |
| Cómo se ejecuta | Docker (Docker Desktop). **No arranca solo al encender el PC**: se abre con el acceso directo "Caudal" y se cierra con "Cerrar Caudal". |
| Acceso | Navegador en `http://localhost:8080`. Desde otros dispositivos de casa, `http://<IP-del-PC>:8080`, solo con el PC encendido y la app abierta. |
| Usuarios | Inicio de sesión con usuario y contraseña. Dos usuarios: `gerard` (admin) y `padres`. Se pueden añadir más. |
| Privacidad entre usuarios | **Cada uno ve solo lo suyo.** No hay vista conjunta. |
| Pestañas | **1. Patrimonio** (portada) · **2. Movimientos** · **3. Inversiones** |
| Cuentas de Gerard | **imagin** y **Wise** (gasto) · **Trade Republic** (efectivo + inversiones + tarjeta) · **Scalable Capital** (inversiones) |
| Cuentas de los padres | **CaixaBank** y **Sabadell** (formatos pendientes) |
| Datos visibles por movimiento | **Cuenta, Concepto, Fecha, Importe** (+ Categoría, asignada automáticamente) |
| Gasto o ingreso | Lo deduce la app por el **signo del importe** |
| Precios de inversiones | Automáticos (Morningstar, Yahoo Finance, CoinGecko), con retraso de ~15 min en bolsa; fondos, una vez al día |
| Backups | Automáticos y **cifrados**, en el **pendrive** (siempre conectado, 250 GB) y en **OneDrive** (cuenta de la universidad) |
| IA | En las primeras fases no se usa IA externa con datos reales. Si más adelante se usa un modelo, será **local**. |
| Stack | PostgreSQL + FastAPI (Python) + React (Vite + Recharts), con Docker Compose |

---

## 3. Las tres pestañas

La app abre siempre en **Patrimonio**. Cada pestaña responde a una pregunta distinta.

### 3.1 Patrimonio (portada): "¿cuánto tengo y cómo evoluciona?"
- **Indicadores:** Patrimonio neto · Liquidez · Inversiones (con plusvalía) · Ahorro este mes.
- **Evolución del patrimonio** a 12 meses (barras apiladas: inversiones + liquidez).
- **Patrimonio por entidad** (imagin, Wise, Trade Republic, Scalable…), separando lo invertido del efectivo.
- **Reparto por tipo:** ETFs, acciones, cripto, fondo monetario, efectivo.
- **Objetivo de patrimonio** con hitos (25.000 €, 50.000 €, 100.000 €…).

### 3.2 Movimientos: "¿en qué gasto y qué entra cada mes?"
- **Indicadores:** Dinero en cuentas · Ingresos del mes · Gastos del mes (vs mes anterior) · Tasa de ahorro.
- **Ingresos vs gastos** a 12 meses y **gasto por categoría**.
- **Presupuestos** por categoría (OK / Al límite / Superado) y **avisos**.
- **Tabla de movimientos** con buscador y etiquetas Auto / Revisar / Manual / Interna.
- **Pagos recurrentes** detectados.
- **Importar extracto** y **añadir movimiento manual**.

### 3.3 Inversiones: "¿cómo va mi cartera?"
- **Barra de estado de precios:** última actualización, qué va con retraso, botón "↻ Actualizar precios".
- **Indicadores:** Valor de las inversiones · Plusvalía (€ y %) · Rentabilidad anual (TIR) · Aportado en 12 meses.
- **Mis posiciones:** producto + ISIN, broker, participaciones, precio medio, precio actual (con etiqueta "~15 min", "En vivo" o "Cierre"), valor, plusvalía y peso.
- **Aportaciones** mes a mes y racha.
- **"¿Y si todo fuera a un indexado?"**: tus mismas aportaciones, en las mismas fechas, en MSCI World, S&P 500 o un monetario.
- **Intereses y dividendos.**
- Si el usuario no tiene inversiones (los padres, de momento), aparece vacía con el botón "Añadir cuenta de inversión".

---

## 4. Usuarios, inicio de sesión y privacidad entre usuarios

### Flujo de entrada
1. Al abrir la app aparece **"¿Quién entra?"** con una tarjeta por usuario (Gerard / Padres).
2. Al elegir una tarjeta se pide la **contraseña**.
3. Al entrar se abre la pestaña **Patrimonio** de ese usuario, **con solo sus datos**.
4. Arriba a la derecha está el usuario y **"Cerrar sesión"**.

### Usuarios iniciales

| Usuario | Quién | Cuentas | Rol |
|---|---|---|---|
| `gerard` | Gerard | imagin, Wise, Trade Republic, Scalable Capital | **admin** (crea usuarios y restablece contraseñas) |
| `padres` | Padres (cuenta compartida) | CaixaBank, Sabadell | normal |

- **Primer arranque:** un asistente crea `gerard` (admin) y `padres` y pide sus contraseñas.
- **Más usuarios en el futuro** (por ejemplo, la hermana): *Ajustes → Usuarios → Nuevo usuario*. Cada usuario nuevo empieza vacío, con sus propias cuentas, categorías, reglas e inversiones.
- **Contraseña olvidada:** el admin la restablece desde *Ajustes → Usuarios*. Si es la del propio admin, se usa el script `Restablecer contraseña` (`.bat` / `.command`).

### Seguridad del inicio de sesión
- Las contraseñas se guardan como **hash Argon2**, nunca en texto plano.
- Sesión en **cookie `HttpOnly` + `SameSite=Strict`**, que **caduca tras 30 minutos sin actividad**.
- **Bloqueo de 5 minutos tras 5 intentos fallidos.**
- **La separación entre usuarios la aplica el servidor:** cada consulta va filtrada por el usuario de la sesión.

### Privacidad entre usuarios
- **Cada uno lo suyo.** No existe la vista conjunta.
- Cuentas, movimientos, categorías, reglas, presupuestos, inversiones y objetivos son **independientes por usuario**.
- Un Bizum de los padres a Gerard es **gasto para los padres** e **ingreso para Gerard**. Es correcto, porque son finanzas separadas.

---

## 5. Cuentas, bancos y brokers

| Usuario | Cuenta | Tipo | Aparece en | Estado del formato |
|---|---|---|---|---|
| gerard | imagin | Gasto | Movimientos + Patrimonio (liquidez) | ✅ conocido |
| gerard | Wise | Gasto + saldo en fondo monetario | Movimientos + Patrimonio (liquidez, "fondo monetario") | ✅ conocido |
| gerard | Trade Republic | **Mixta**: efectivo remunerado + tarjeta + cartera | Movimientos (tarjeta y efectivo) + Inversiones (cartera) + Patrimonio | ⏳ falta un ejemplo |
| gerard | Scalable Capital | Inversión (+ algo de efectivo) | Inversiones + Patrimonio | ⏳ falta un ejemplo |
| padres | CaixaBank | Gasto | Movimientos + Patrimonio | ⏳ falta un ejemplo |
| padres | Sabadell | Gasto / ahorro | Movimientos + Patrimonio | ⏳ falta un ejemplo |

**Tipos de cuenta en la app:**
- **gasto:** sus movimientos van a la pestaña Movimientos; su saldo cuenta como liquidez.
- **inversión:** sus operaciones van a Inversiones; su efectivo cuenta como liquidez.
- **mixta** (Trade Republic): los pagos con tarjeta, los ingresos y los intereses van a Movimientos; las compras y ventas de valores, a Inversiones.

**El fondo monetario de Wise** cuenta como **liquidez** (marcado "fondo monetario"): es dinero disponible para gastar, no una inversión a largo plazo.

> ⚠️ **Los ejemplos usan siempre datos inventados.** Los archivos de `samples/` se hacen copiando un extracto real, dejando unas pocas filas que cubran los casos de prueba y cambiando conceptos, importes, nombres e IDs, **sin tocar el formato**.

---

## 6. Formatos de los extractos bancarios

### 6.0 Cómo se importa y cómo se reconoce cada archivo
- **El extracto se sube tal cual lo da el banco.** No hay que borrar columnas ni filas, ni editarlo en Excel. Solo se editan los ejemplos de `samples/`, porque van al repositorio y tienen que ser inventados.
- **Las columnas se leen por el nombre de la cabecera, no por su posición.** Se usan las que indica cada sección y las demás se ignoran. Si el banco añade o reordena columnas, sigue funcionando. Si falta una columna necesaria, la importación se detiene con un mensaje claro (*"No se encuentra la columna «Importe»"*).
- **Al importar, el usuario elige la cuenta** (cada cuenta sabe de qué banco es) y la app **comprueba que el archivo es de ese banco** antes de leer nada:
  - **imagin:** una sola hoja con las cabeceras `Concepto`, `Fecha`, `Importe` y `Saldo` en la fila 1.
  - **Wise:** hoja `All transactions` con, al menos, `Documento de identidad`, `Fecha`, `Cantidad` y `Divisa`.
  - Si no coincide, avisa sin importar nada: *"Este archivo parece de Wise, pero has elegido la cuenta imagin"*.

### 6.1 imagin
- **Cómo se descarga:** app/web de imagin → Movimientos → descargar → **Excel** (también ofrece PDF, que no se usa; **no hay CSV**). Archivo `extractDocument_AAAAMMDD.xlsx`.
- **Formato:** Excel `.xlsx`, una hoja, **cabeceras en la fila 1** (no hay filas que saltar). Del más reciente al más antiguo. **Todas las celdas son texto** (confirmado en la Fase 0).

| Columna | Ejemplo (inventado) | Notas |
|---|---|---|
| `Concepto` | `BIZUM ENVIAT` / `BIZUM REBUT` / `BON AREA` / `WWW.AMAZON` / `enviament de dine` | En **catalán** y **no siempre en mayúsculas**. Puede venir **cortado** (`enviament de dine` = transferencia enviada, sin destinatario). |
| `Fecha` | `29/09/2026` | **Texto** con formato `dd/mm/aaaa`. Por robustez, aceptar también una fecha de Excel si algún día cambia. |
| `Importe` | `-23,00EUR` / `69,73EUR` | **Texto con la divisa pegada y siempre dos decimales:** quitar `EUR`, quitar los puntos de miles y cambiar la coma decimal por punto. Negativo = gasto. |
| `Saldo` | `42,46EUR` | Mismo formato. **No se guarda**: se usa para la huella anti-duplicados y para comprobar que no falta ningún movimiento. |

### 6.2 Wise
- **Cómo se descarga:** web de Wise → Estados de cuenta → Excel. Archivo `statement_<número>_EUR_<desde>_<hasta>.xlsx` (**uno por divisa**).
- **Formato:** `.xlsx`, hoja **`All transactions`**, **cabeceras en la fila 1**, 32 columnas. Fechas = fechas reales de Excel; importes = números. Del más reciente al más antiguo. Algunas celdas vacías vienen como **texto vacío** (`''`) y no como celda vacía: tratar los dos casos igual (confirmado en la Fase 0).

**Columnas que se usan:**

| Columna | Ejemplo (inventado) | Uso |
|---|---|---|
| `Documento de identidad` | `CARD-123456` | **ID de la transacción** (no es un DNI) → huella anti-duplicados |
| `Fecha` | `25/09/2026` | Fecha |
| `Fecha y hora` | `25/09/2026 13:42:55.294` | Opcional: ordenar movimientos del mismo día |
| `Cantidad` | `-2.08` | Importe (negativo = gasto) |
| `Divisa` | `EUR` | En la Fase 1 solo EUR |
| `Descripción` | `Transacción con tarjeta de 2,08 EUR emitida por ...` | Concepto de respaldo |
| `Comercio` | `Tienda Ejemplo CIUDAD` | **Concepto preferente** |
| `Nombre del pagador` / `Nombre del beneficiario` | `Nombre Ejemplo` | Concepto si no hay comercio |
| `Tipo de transacción` | `DEBIT` / `CREDIT` | Comprobar el signo |
| `Tipo de detalles de transacción` | `CARD`, `DEPOSIT`, `TRANSFER`… | Detectar transferencias y conversiones. Un ingreso desde imagin llega como `CREDIT` + `DEPOSIT` |
| `Referencia del pago` | `enviament de diners - imaginBank` | **Solo para detectar** transferencias desde imagin (contiene `imaginBank`); no se guarda |
| `Cambiar desde` / `Cambiar a` / `Tipo de cambio` | | Conversiones de divisa = transferencia interna |
| `Comisiones totales` | `0` | Opcional |

**Concepto en Wise:** `Comercio` → si está vacío, `Nombre del beneficiario` (gasto) o `Nombre del pagador` (ingreso) → si también está vacío, `Descripción`.

**Se ignoran y no se guardan:** `Referencia del pago` (solo se usa para detectar transferencias), `Saldo corriente` (solo para verificar), `Número de cuenta del beneficiario`, `Últimos cuatro dígitos de la tarjeta`, `Nombre completo del titular de la tarjeta`, `Archivo adjunto`, `Nota`, y **todas las columnas del fondo** (`Tipo/Valor de ID del activo negociado` [ISIN], `Unidades negociadas`, `Tipo de negociación` [SELL], precios unitarios, `Tipo de cambio efectivo`, `Valor convertido`).

> Cada pago con tarjeta de Wise **vende participaciones del fondo monetario** para cubrir el pago. Eso es solo la mecánica de Wise y **no es un gasto aparte**. En el extracto, la venta aparece **en la misma fila** que el pago (columnas del fondo rellenas, `Tipo de negociación` = `SELL`), no en una fila propia: se ignoran esas columnas y la fila es un gasto normal. Si aparecen filas propias de intereses o de compra/venta del fondo, se marcan como **rendimiento** o **transferencia interna**.

### 6.3 Trade Republic y Scalable Capital
- **Pendiente:** ver qué permite exportar cada uno (CSV/Excel de transacciones o solo PDFs) y conseguir un ejemplo con **datos inventados**.
- **Trade Republic** genera dos tipos de filas: **movimientos de efectivo** (tarjeta, ingresos, intereses → Movimientos) y **operaciones de valores** (compras, ventas, planes de inversión, dividendos → Inversiones). El importador tiene que separarlas.
- Si alguno solo ofrece PDFs: introducción **manual** o con la **plantilla de Excel** (sección 7.4).

### 6.4 CaixaBank y Sabadell (padres)
- **Pendiente:** un ejemplo de cada uno con datos inventados (cabeceras + 2 o 3 filas, tal cual). Anotar cuántas filas hay antes de las cabeceras.

### 6.5 Asistente de importación genérico
Para cualquier banco nuevo: se sube el archivo y se indica qué columna es la **fecha**, el **importe** (o cargo + abono) y el **concepto**, cuántas filas hay que **saltar** y el formato de la fecha y los decimales. La app **recuerda el formato**.

---

## 7. Inversiones

### 7.1 Qué se puede registrar
ETFs, acciones, fondos indexados, cripto, planes de pensiones, depósitos, oro… Para lo que no cotiza o no tiene precio en internet (plan de pensiones, depósito), se usa **"valor anotado a mano"**: se anota su valor con fecha, por ejemplo una vez al mes.

### 7.2 Productos y operaciones
- **Producto:** nombre, **ISIN** o ticker, tipo (ETF, acción, fondo, cripto, plan, otro), divisa, fuente del precio y TER (comisión anual) si se conoce.
- **Operación:** fecha, cuenta (broker), producto, tipo (**compra**, **venta**, **dividendo**, **comisión**), participaciones e **importe total en euros** (en una compra, lo que salió de la cuenta con comisiones incluidas; en una venta o dividendo, lo que entró).
- **Buscador por ISIN, ticker o nombre:** antes de guardar comprueba que el producto tiene precio y rellena tipo, divisa y TER.

### 7.3 Precios
| Tipo | Fuente | Frescura |
|---|---|---|
| ETFs y acciones | Yahoo Finance | ~15 min de retraso |
| Fondos | Morningstar | Valor liquidativo del cierre (1 vez al día, con 1–2 días de retraso) |
| Cripto | CoinGecko | Prácticamente en vivo |
| Divisas | Yahoo Finance | Para pasar todo a EUR |

- Se actualizan **al abrir la app** (si tienen más de 6 horas), **cada 15 minutos** mientras está abierta y con el botón **"↻ Actualizar precios"**.
- **El histórico** de precios se descarga y se guarda, para poder dibujar la evolución aunque el PC haya estado apagado.
- ⚠️ **Son fuentes gratuitas y no oficiales:** pueden fallar o cambiar. La app guarda el **último precio conocido**, muestra su fecha y **avisa** si está desactualizado.
- **Privacidad:** en las consultas solo viajan identificadores (ISIN o ticker), **nunca cantidades ni importes**.

### 7.4 Cómo entran los datos
1. **A mano:** formulario "+ Añadir compra / venta".
2. **Importador** del CSV de Trade Republic / Scalable (cuando se conozca su formato).
3. **Plantilla de Excel/CSV** propia: `fecha; identificador; nombre; tipo_producto; tipo_movimiento; unidades; importe; moneda; comision; nota`.
4. **Importar desde RUMBO:** si se ha usado RUMBO mientras tanto, se importa su `mis_datos/cartera.json` (productos y movimientos) para no perder nada.

### 7.5 Cálculos
- **Valor actual** = participaciones × último precio (en EUR).
- **Coste y ventas por FIFO** (se venden primero las participaciones más antiguas), como exige Hacienda.
- **Plusvalía latente** (de lo que aún se tiene) y **realizada** (de lo vendido).
- **TIR (XIRR):** rentabilidad anual que tiene en cuenta **cuándo** entró y salió cada euro.
- **Rentabilidad por año natural** y **peor caída** (máximo drawdown).
- **Comparativa con un indexado:** se repiten las mismas aportaciones y ventas, en las mismas fechas, en MSCI World (IWDA), S&P 500 (SXR8) y un monetario del euro (XEON), y se compara con el valor real.
- **Comisiones anuales:** suma de valor × TER de cada producto.
- **Aportaciones** mes a mes, racha de meses aportando e **hitos** de patrimonio.
- Más adelante: **ganancias realizadas por año** para la declaración de la renta (solo informativo).

> **Aviso en la app:** Caudal muestra datos, **no da recomendaciones** de compra o venta ni es asesoramiento financiero. Los precios pueden diferir de los del broker.

---

## 8. Qué se guarda (modelo de datos)

### 8.1 Movimientos: lo que ve el usuario

| Cuenta | Concepto | Fecha | Importe | Categoría |
|---|---|---|---|---|
| Wise | Tienda Ejemplo CIUDAD | 25/09/2026 | −2,08 € | Supermercado *(auto)* |

**Negativo = gasto, positivo = ingreso.** El tipo no se guarda aparte.

### 8.2 Movimientos: lo que se guarda internamente (invisible)

| Dato interno | Para qué es imprescindible |
|---|---|
| **Usuario** (a través de la cuenta) | Separar los datos de cada usuario |
| **Estado de la categoría**: `auto` / `manual` / `revisar` | Saber qué hay que revisar |
| **Huella anti-duplicados** | Que importar dos veces lo mismo **no duplique** nada |
| **Marca de transferencia interna** | Que mover dinero entre cuentas propias (imagin → Wise, imagin → Trade Republic) **no cuente** como gasto + ingreso |

El saldo **se calcula**, no se guarda por movimiento. Se guarda un **saldo de referencia por cuenta** (último saldo del extracto o anotado a mano) para comprobar que cuadra.

### 8.3 Lo que NO se guarda nunca
- Nombre del titular, dígitos de la tarjeta, números de cuenta o IBAN.
- Columnas del fondo de Wise.
- **El archivo original del extracto:** se lee, se importa y se descarta.

> Hora, divisa original, notas, etiquetas y "deshacer importación" quedan **fuera** por ahora. Se pueden añadir después sin perder datos (con una migración de Alembic).

### 8.4 Tablas (esquema orientativo)

```text
usuarios
  id, nombre_usuario (único), nombre_visible, hash_contraseña, es_admin,
  intentos_fallidos, bloqueado_hasta, creado_en

cuentas
  id, usuario_id → usuarios, nombre ("imagin", "Trade Republic"...),
  tipo ("gasto" | "inversion" | "mixta"), formato_importacion,
  subtipo_liquidez ("efectivo" | "fondo_monetario"),
  saldo_referencia (NUMERIC), saldo_referencia_fecha

categorias
  id, usuario_id, nombre, tipo ("gasto" | "ingreso"), color, presupuesto_mensual (Fase 2)

movimientos
  id, cuenta_id → cuentas, fecha, concepto, importe NUMERIC(12,2),
  categoria_id (nullable), estado_categoria ("auto" | "manual" | "revisar"),
  es_transferencia_interna (bool), huella, UNIQUE (cuenta_id, huella)

reglas
  id, usuario_id, texto_contiene, categoria_id, prioridad, creada_por ("sistema" | "usuario")

formatos_importacion   (asistente genérico)
  id, usuario_id, nombre, filas_a_saltar, col_fecha, formato_fecha,
  col_importe | col_cargo + col_abono, col_concepto, separador_decimal

-- Inversiones (Fase 3) --
productos
  id, usuario_id, nombre, isin, ticker, tipo ("etf" | "accion" | "fondo" | "cripto" | "pension" | "otro"),
  divisa, fuente_precio ("yahoo" | "morningstar" | "coingecko" | "manual"), id_fuente, ter (NUMERIC, nullable),
  largo_plazo (bool)

operaciones_inversion
  id, cuenta_id → cuentas, producto_id → productos, fecha,
  tipo ("compra" | "venta" | "dividendo" | "comision"),
  participaciones NUMERIC(18,8), importe_eur NUMERIC(12,2), comision_eur NUMERIC(12,2) (nullable),
  huella, UNIQUE (cuenta_id, huella)

precios
  producto_id → productos, fecha, precio NUMERIC(18,6), divisa, fuente, PRIMARY KEY (producto_id, fecha)

valores_manuales        (plan de pensiones, depósitos…)
  id, producto_id, fecha, valor_eur, aportado_eur (nullable)

objetivos
  id, usuario_id, importe_meta, nombre

registro_backups
  id, fecha_hora, destino ("pendrive" | "onedrive"), resultado ("ok" | "error"), mensaje
```

- Dinero en **`NUMERIC`**, nunca `float`. En Python, **`Decimal`**.
- **Nombres en el código:** las tablas y campos se escriben en **inglés** en el código y la base de datos (`users`, `accounts`, `transactions`…). La equivalencia con los nombres en castellano de este documento está en `CLAUDE.md` (sección "Convenciones").
- Esquema gestionado con **Alembic** (migraciones).

---

## 9. Lógica automática

### 9.1 Gasto o ingreso
`importe < 0` → gasto; `importe > 0` → ingreso. Los totales **excluyen** las transferencias internas.

### 9.2 Huella anti-duplicados

| Origen | Huella |
|---|---|
| Wise | `Documento de identidad` (ID único) |
| imagin | `sha256(cuenta | fecha | importe | concepto normalizado | saldo del extracto)` |
| Genérico | `sha256(cuenta | fecha | importe | concepto normalizado | nº de aparición en el archivo)` |
| Brokers | ID de la operación si existe; si no, `sha256(cuenta | fecha | producto | tipo | participaciones | importe)` |

En imagin, el **saldo** hace que dos compras idénticas el mismo día no se tomen por duplicados. Al importar se informa: *"142 leídos · 120 nuevos · 22 ya existían"*.

### 9.3 Transferencias internas
Dentro del **mismo usuario**, se emparejan dos movimientos de **cuentas distintas** con **importes opuestos** y **≤ 3 días** de diferencia (y, si ayuda, un concepto como `TRANSFERENCIA`, una recarga de Wise o el nombre del propio titular). En imagin el concepto de una transferencia enviada (`enviament de dine`) **no dice el destino**, así que allí cuentan solo el importe y la fecha. En Wise, el ingreso correspondiente lleva `Referencia del pago` con `imaginBank`, lo que confirma la pareja. Se marcan los dos y el usuario puede desmarcarlo. También son internas: las conversiones de divisa de Wise y el dinero que se pasa a un broker para invertir.

### 9.4 Categorización
1. **Reglas** "si el concepto contiene X → categoría Y", por prioridad, comparando en mayúsculas y sin acentos.
2. Si ninguna encaja → **`revisar`**.
3. **Aprende de las correcciones:** al cambiar una categoría, la app ofrece *"¿Aplicar siempre a 'BON AREA'?"*. Si se acepta, crea la regla y la reaplica a los pendientes.

**Categorías iniciales (editables):**
- **Gastos:** Supermercado, Comida fuera, Ocio y salidas, Transporte, Vivienda, Suministros, Suscripciones, Compras online, Ropa, Salud, Educación / Material uni, Regalos, Otros.
- **Ingresos:** Nómina, Bizum recibido, Transferencias recibidas, Intereses, Otros ingresos.

**Reglas iniciales de ejemplo:** `BON AREA`, `MERCADONA`, `CONSUM` → Supermercado · `MC DONALDS`, `BAR` → Comida fuera · `AMAZON`, `WWW.AMAZ` → Compras online · `REPSOL`, `RENFE` → Transporte · `SPOTIFY`, `NETFLIX` → Suscripciones · `BIZUM ENVIAT` / `BIZUM REBUT` (imagin, en catalán) → **revisar**.

### 9.5 Pagos recurrentes (Fase 2)
Mismo concepto e importe parecido (±10 %) con periodicidad mensual o anual → pago recurrente, con el total al mes.

---

## 10. Arquitectura y stack

```text
 Navegador (PC / móvil en la red de casa)
            │  http://localhost:8080
            ▼
 ┌─────────────────────────────┐        ┌──────────────────────┐
 │ app (contenedor Docker)     │        │ db (contenedor)      │
 │ FastAPI: API REST + sirve   │──SQL──▶│ PostgreSQL 16        │
 │ el frontend React compilado │        │ volumen: pgdata      │
 │ + tareas: backups, precios  │        └──────────────────────┘
 └─────────────────────────────┘
      │ backups cifrados            │ precios (solo ISIN/ticker)
      ▼                             ▼
  pendrive + OneDrive         Yahoo / Morningstar / CoinGecko
```

| Capa | Tecnología |
|---|---|
| Base de datos | PostgreSQL 16 |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic, APScheduler (tareas periódicas) |
| Lectura de extractos | pandas + openpyxl (`.xlsx`), xlrd (`.xls`) |
| Contraseñas | argon2-cffi |
| Precios | httpx (con caché, tiempo de espera y reintentos) |
| Cálculos financieros | `Decimal`; XIRR implementado y testeado (o `pyxirr`) |
| Cifrado de backups | `cryptography` (AES-256-GCM, clave derivada con scrypt) |
| Frontend | React + Vite + TypeScript, Recharts |
| Orquestación | Docker Compose (`app` + `db`) |

**Estructura de carpetas prevista:**

```text
caudal/
├── README.md                   ← presentación del proyecto
├── CLAUDE.md                   ← cómo trabaja Claude, fase a fase
├── CHANGELOG.md
├── INSTRUCCIONES_PROYECTO_CLAUDE.md
├── docs/DISENO.md              ← este documento
├── docs/capturas/
├── maqueta/caudal-maqueta.html
├── docker-compose.yml
├── .env.example                ← el .env real NUNCA se sube a git
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/
│   └── app/
│       ├── main.py
│       ├── auth/               ← login, sesiones, usuarios
│       ├── importers/          ← imagin.py, wise.py, trade_republic.py, scalable.py, caixabank.py, sabadell.py, generico.py, rumbo.py
│       ├── categorization/
│       ├── transfers/
│       ├── investments/        ← productos, operaciones, FIFO, XIRR, comparativa
│       ├── prices/             ← yahoo.py, morningstar.py, coingecko.py, caché
│       ├── backup/
│       └── api/
├── frontend/src/               ← login, Patrimonio, Movimientos, Inversiones, Ajustes
├── scripts/
│   ├── windows/  Caudal.bat, Cerrar Caudal.bat, Restaurar backup.bat, Restablecer contraseña.bat
│   └── mac/      Caudal.command, Cerrar Caudal.command, ...
├── samples/                    ← ejemplos con DATOS INVENTADOS
└── tests/
```

**Configuración (`.env`, orientativo):**

```dotenv
APP_PORT=8080
POSTGRES_USER=caudal
POSTGRES_PASSWORD=<generada en la instalación>
POSTGRES_DB=caudal
SESSION_SECRET=<generada en la instalación>
SESSION_TIMEOUT_MIN=30

PRICE_REFRESH_MIN=15
PRICE_MAX_AGE_HOURS=6

BACKUP_PASSWORD=<la eliges tú y la apuntas en papel>
BACKUP_INTERVAL_MIN=60
BACKUP_KEEP=30
BACKUP_MAX_AGE_DAYS=7
USB_LABEL=Gerard
ONEDRIVE_DIR=C:\Users\gerar\OneDrive - udl.cat\Proyectos\CaudalBackups
```

---

## 11. Arranque y parada (Docker solo cuando quieras)

**Requisito:** en Docker Desktop, desactivar *Settings → General → "Start Docker Desktop when you sign in"*. Así, al encender el PC para jugar, no se carga nada.

### Acceso directo "Caudal" (doble clic)
1. Abre Docker Desktop si no está abierto y **espera** a que esté listo.
2. **Busca el pendrive por su nombre de volumen** (`USB_LABEL`), no por su letra. Si no lo encuentra, sigue igualmente y el panel avisa.
3. `docker compose up -d`.
4. Cuando la app responde, **abre el navegador** en `http://localhost:8080`.

### Acceso directo "Cerrar Caudal" (doble clic)
1. **Backup final.**
2. `docker compose down` (los datos se conservan en el volumen).
3. Opcional: cierra Docker Desktop para liberar memoria.

### Desde otros dispositivos de casa
`http://<IP-del-PC>:8080` con el PC encendido y la app abierta. En el firewall de Windows, permitir **solo en redes privadas**. **Nunca** abrir puertos en el router.

---

## 12. Copias de seguridad (pendrive + OneDrive)

### Cuándo (automático)

| Momento | Motivo |
|---|---|
| **Después de cada importación** (extractos o inversiones) | Es cuando más datos cambian |
| **Cada 60 min** mientras la app está abierta, solo si hubo cambios | Cubre ediciones y movimientos manuales |
| **Al cerrar** con "Cerrar Caudal" | Copia final |
| **Al arrancar**, si la última copia tiene más de 7 días | Red de seguridad por si se apagó el PC sin cerrar la app |

> **¿Por qué no "en tiempo real"?** Los datos solo cambian con la app abierta, y con estos cuatro momentos como mucho se perderían minutos de trabajo. Un backup continuo complicaría el sistema sin aportar nada.

### Dónde
1. **Pendrive** (siempre conectado, 250 GB), detectado por **nombre de volumen** (`USB_LABEL`, ahora `Gerard`) → carpeta `CaudalBackups/`. El pendrive puede tener más archivos: Caudal solo escribe en esa carpeta.
2. **OneDrive** (cuenta de la universidad) → carpeta sincronizada `CaudalBackups/`.

Si un destino falla, se escribe igualmente en el otro y el panel lo indica.

### Cómo
- `pg_dump` (formato custom) → **AES-256-GCM** con clave derivada de `BACKUP_PASSWORD` → `caudal_AAAA-MM-DD_HHMM.dump.enc`.
- **Rotación:** las **30 últimas** por destino.
- **Indicador:** `Último backup: hoy 18:42 · Pendrive ✓ · OneDrive ✓`.

### Contraseña de backup
- **Distinta** de las de inicio de sesión.
- Está en el `.env` para que los backups sean automáticos. Protege las copias del pendrive y de OneDrive, pero no a quien tenga acceso al propio PC.
- **Apuntarla en papel en un sitio seguro.** Si se pierde, las copias no se pueden abrir.

### Restaurar
Script **"Restaurar backup"**: se elige el archivo, se escribe la contraseña y hace `pg_restore` sobre una base vacía. **Se prueba de verdad en la Fase 1d** y en la mudanza al Mac.

### Avisos
- **OneDrive de la universidad:** al acabar la carrera la UdL desactivará la cuenta. **Antes de graduarse** hay que mover los backups a otro sitio. Conviene revisar las normas de uso de la UdL sobre archivos personales. Al ir cifrados, nadie puede leerlos.
- **Pendrive:** es fiable, pero falla más que un disco. Por eso hay dos destinos.

---

## 13. Seguridad y privacidad

**Reglas obligatorias:**
1. **Nunca subir datos reales a git ni pegarlos en conversaciones.** Ejemplos siempre inventados.
2. `.gitignore` excluye `.env`, `pgdata/`, `backups/`, `*.dump`, `*.enc`, y `*.xlsx` / `*.xls` / `*.csv` **excepto** los de `samples/`.
3. **Solo red local.** Nada de abrir puertos ni publicar la app.
4. **Nada de IA externa con datos reales.** Si se usa IA, será un modelo **local** (por ejemplo, Ollama).
5. **Mínimo de datos** (sección 8.3).
6. **Argon2**, sesiones que caducan y bloqueo por intentos fallidos.
7. **Backups cifrados** con contraseña propia.
8. **Permisos por usuario en el backend**, con **tests** que lo comprueben.
9. Para los precios, solo se envían **identificadores** de producto, nunca importes.

**Riesgo real de un extracto:** no permite mover dinero, pero revela hábitos, ubicación aproximada, ingresos y patrimonio. Eso se puede usar para estafas dirigidas. Por eso se protege.

---

## 14. La maqueta

- **Archivo:** `maqueta/caudal-maqueta.html` (doble clic; solo carga las fuentes de Google Fonts si hay internet).
- **Versión editable en Claude:** https://claude.ai/artifact/DXDvWvm4wy3PE4RYRtcckQ (pulsar ▶ Play para usarla).
- **Todos los datos son inventados.** Se puede entrar como Gerard o Padres con cualquier contraseña.
- **Es la referencia visual oficial:** la app real debe parecerse a ella. Se puede mejorar, pero sin cambiar la estructura de las tres pestañas sin actualizar este documento.

**Estilo:** fondo `#F3F4F1`, tarjetas blancas con borde `#E3E5E0` y radio de 14 px, texto `#15181C`, gris `#5B616B`, barra lateral `#15181C`. Acento verde `#0E6B58` (ingresos y positivo), naranja `#C2581B` (gastos), rojo `#B42318` (superado o negativo), azul `#3555A0` (inversiones), verde claro `#9DB8AE` (liquidez). Tipografías **Space Grotesk** (títulos y cifras) y **Manrope** (texto). Formato español: `1.234,56 €`.

**Qué elemento va en qué fase:**

| Elemento | Fase |
|---|---|
| Acceso "¿Quién entra?" + contraseña, cerrar sesión | 1a |
| Estructura de 3 pestañas + barra lateral | 1c |
| Movimientos: indicadores, ingresos vs gastos, gasto por categoría, tabla, importar, añadir manual | 1b–1c |
| Patrimonio: indicadores, evolución, por entidad, reparto (solo liquidez al principio) | 1c |
| Indicador de backup | 1d |
| Presupuestos, avisos, recurrentes, objetivo de patrimonio | 2 |
| Pestaña Inversiones completa + inversiones en Patrimonio | 3 |

---

## 15. Roadmap por fases

> **Una fase o bloque por conversación** dentro del proyecto de Claude. Una fase está terminada cuando se cumplen sus criterios de "hecho". El detalle de cada fase (entregables, pasos, tests y cierre) está en `CLAUDE.md`.

### Fase 0: preparar el entorno (sin programar)
- [ ] Instalar **Docker Desktop** (Windows, WSL2) y **desactivar el arranque automático**.
- [ ] Instalar **Git** y **VS Code**. Repositorio **privado** en GitHub (opcional; nunca con datos).
- [ ] Mantener el nombre de volumen actual del pendrive, **`Gerard`** (exFAT, 250 GB), y crear `CaudalBackups/` en él. Ningún otro pendrive debe llamarse igual, o la app podría guardar el backup en el que no toca.
- [ ] Crear `CaudalBackups/` en OneDrive y anotar su ruta exacta.
- [ ] Elegir y **apuntar en papel** la contraseña de backup.
- [ ] Preparar `samples/imagin_ejemplo.xlsx` y `samples/wise_ejemplo.xlsx` con **datos inventados**.
- [x] Confirmar si la `Fecha` de imagin es fecha de Excel o texto → **texto `dd/mm/aaaa`** (sección 6.1).
- [ ] Mirar qué exportan **Trade Republic** y **Scalable** y guardar ejemplos inventados (no bloquea hasta la Fase 3).
- **Hecho cuando:** `docker run hello-world` funciona y existen los ejemplos de imagin y Wise.

### Fase 1: MVP útil (Gerard)
**1a. Base + inicio de sesión**
- Docker Compose (`app` + `db`), `.env.example`, `.gitignore`, Alembic con las tablas de movimientos.
- Asistente de primer arranque, login, sesión, caducidad, bloqueo y cerrar sesión. Pantalla "¿Quién entra?" como en la maqueta.
- **Hecho cuando:** se entra con los dos usuarios, cada uno ve su panel vacío y hay tests de permisos.

**1b. Importadores imagin + Wise**
- Lectura y limpieza, concepto de Wise, huella, deduplicación, ignorar columnas del fondo y transferencias internas.
- Pantalla de importar con el resumen "leídos / nuevos / ya existían".
- **Filas que no se pueden leer:** nunca se descartan en silencio. El resumen indica la fila y el dato que ha fallado (*"Fila 5: no se ha podido leer el importe «-23 EUR»"*) y ofrece **añadir ese movimiento a mano** desde la misma pantalla. Si el saldo de imagin no cuadra entre dos filas, avisa de que puede faltar un movimiento.
- **Hecho cuando:** importar dos veces no duplica, los tests con `samples/` pasan y el saldo calculado cuadra con el extracto.

**1c. Categorización + pestañas Movimientos y Patrimonio**
- Categorías, reglas, revisión y "¿Aplicar siempre?".
- **Estructura de 3 pestañas.** **Movimientos**: indicadores, gráficos, tabla con buscador y alta, edición y borrado manual. **Patrimonio**: con la liquidez de las cuentas (saldos de referencia). **Inversiones**: vacía con su mensaje.
- **Hecho cuando:** tras importar un mes real, todo lo que no sea Bizum queda categorizado y los gráficos coinciden con los totales.

**1d. Backups + accesos directos**
- Backup cifrado, rotación, los 4 momentos, pendrive por nombre, indicador. Scripts de Windows.
- **Hecho cuando:** se ha hecho una **restauración completa de prueba** desde el pendrive y desde OneDrive.

### Fase 2: control del gasto
- Presupuestos (OK / Al límite ≥ 90 % / Superado), avisos y pagos recurrentes.
- Selector de mes y comparativa con el anterior. Objetivo de patrimonio con hitos.
- **Hecho cuando:** Movimientos se parece a la maqueta completa con datos reales.

### Fase 3: patrimonio e inversiones (Gerard)
- Tablas de inversiones (sección 8.4), cuentas **mixtas** (Trade Republic) y de **inversión** (Scalable).
- Buscador de productos y **servicio de precios** (Yahoo, Morningstar, CoinGecko) con caché, histórico, avisos de precio desactualizado y actualización cada 15 min.
- Alta manual de operaciones, **plantilla de Excel**, importadores de **Trade Republic** y **Scalable** (si exportan CSV) e **importación de RUMBO**.
- Cálculos: valor, FIFO, plusvalía latente y realizada, **XIRR**, rentabilidad anual, peor caída, comparativa con indexado, comisiones (TER), aportaciones y racha.
- Pestaña **Inversiones** completa y **Patrimonio** con inversiones (evolución apilada, por entidad, reparto por tipo).
- **Hecho cuando:** el valor de la cartera difiere menos del 1 % del que muestran los brokers el mismo día, y los tests de FIFO y XIRR pasan con casos calculados a mano.

### Fase 4: los padres
- Importadores de **CaixaBank** y **Sabadell** + **asistente genérico**.
- Gestión de usuarios en *Ajustes*.
- Usabilidad para los padres: textos claros, botones grandes, uso desde el móvil en la red de casa.
- **Hecho cuando:** los padres importan y revisan un mes solos.

### Fase 5: inteligencia y extras
- **Previsión** del gasto del mes siguiente.
- **Categorización con un modelo local** (Ollama) como sugerencia para los movimientos en `revisar`.
- **Exportar** informes (PDF / Excel), ganancias realizadas por año (informativo) y multidivisa en Wise.
- Opcionales: etiquetas, notas, deshacer importación, tema oscuro y "solo largo plazo" en inversiones.

### Fase 6: migración a Mac
Ver sección 16.

### Fase 7 (opcional): versión para el CV
Instancia **separada** con datos **100 % inventados**, README público para GitHub, capturas, tests y CI. **Nunca** conectada a la real.

---

## 16. Paso a Mac

1. En Windows: **"Cerrar Caudal"** (hace el backup final).
2. En el Mac: Docker Desktop (con el arranque automático **desactivado**) y Git; clonar o copiar el proyecto.
3. Copiar el `.env` ajustando:
   - `ONEDRIVE_DIR=/Users/<usuario>/Library/CloudStorage/OneDrive-<organización>/Proyectos/CaudalBackups` (comprobar el nombre exacto en Finder).
   - El pendrive aparece en `/Volumes/Gerard`.
4. **"Restaurar backup"** con el último backup.
5. Abrir con `Caudal.command` (la primera vez, `chmod +x` y permitirlo en *Privacidad y seguridad*).
6. Comprobar que los totales coinciden con los del PC.

---

## 17. Pendientes y decisiones abiertas

| # | Pendiente | Cuándo |
|---|---|---|
| 1 | ~~Ruta exacta de OneDrive~~ → `C:\Users\gerar\OneDrive - udl.cat\Proyectos\CaudalBackups` | ✅ Fase 0 |
| 2 | ~~¿La `Fecha` de imagin es fecha o texto? ¿imagin exporta CSV?~~ → texto `dd/mm/aaaa`; solo Excel o PDF | ✅ Fase 0 |
| 3 | Qué exportan Trade Republic y Scalable + ejemplos inventados | Antes de la Fase 3 |
| 4 | Ejemplos de CaixaBank y Sabadell | Antes de la Fase 4 |
| 5 | Confirmar las categorías iniciales | Fase 1c |
| 6 | Objetivo de patrimonio de cada usuario | Fase 2 |
| 7 | Destino de los backups tras graduarse (sustituir OneDrive UdL) | Antes de acabar la carrera |

---

## 18. Referencias

- **RUMBO** (Dani Dominguez Quant), https://github.com/danidm98/rumbo, **licencia MIT**. App local de patrimonio e inversiones (Python + Flask) que inspiró la parte de inversiones de Caudal: fuentes de precios (Morningstar, Yahoo, CoinGecko), FIFO, TIR, comparativa con indexado, valores anotados a mano, plantilla de importación. **Si se reutiliza código suyo, hay que mantener su aviso de copyright y licencia MIT** en los archivos copiados o en un `THIRD_PARTY_NOTICES.md`.
- Mientras Caudal no tenga la Fase 3, se puede usar RUMBO para las inversiones y luego importar su `cartera.json`.

---

## 19. Instrucciones para Claude en este proyecto

- **Idioma:** español.
- **Sistema:** Windows ahora; todo debe funcionar también en **macOS** (scripts para los dos y rutas en `.env`).
- **Forma de trabajar:** una fase o bloque por conversación. Seguir `CLAUDE.md`, leer este documento al empezar y respetar sus decisiones. Si algo cambia, proponer la actualización de este documento.
- **Entregables:** archivos completos, listos para usar, con **pasos exactos** para ejecutarlos. Sin TODOs ni plantillas a medias.
- **Diseño:** seguir la maqueta (`maqueta/caudal-maqueta.html`) y el estilo de la sección 14.
- **Formatos bancarios:** no inventarlos. Si falta un ejemplo, pedirlo con datos inventados.
- **Privacidad:** no pedir ni usar datos reales. Si el usuario los pega, avisarle y no reutilizarlos.
- **Calidad:** tests para importadores, huellas, transferencias internas, permisos, FIFO y XIRR. Dinero en `Decimal` / `NUMERIC`.
- **Honestidad:** señalar riesgos reales y compromisos en lugar de dar por buena cualquier opción.
