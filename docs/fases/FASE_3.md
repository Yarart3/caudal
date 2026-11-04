# Fase 3 · Patrimonio e inversiones

> **Versión:** `0.6.0` · **Inicio:** 2026-11-03 · **Estado:** 🔄 en curso

## Partes

| Parte | Qué | Estado |
|---|---|---|
| 3.1 | Migración `0004`: `products`, `investment_operations`, `prices`, `manual_valuations` | ✅ |
| 3.2a | `app/prices/yahoo.py`: precio, histórico y búsqueda por ISIN, y el comando `python -m app.prices` | ✅ |
| 3.2b | Servicio de precios: guardar en `prices`, caché, aviso de precio desactualizado, refresco y `/api/prices/*` | ⬜ |
| 3.3 | Productos y operaciones: buscador, API, formulario con «duplicar», plantilla y RUMBO | ⬜ |
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
