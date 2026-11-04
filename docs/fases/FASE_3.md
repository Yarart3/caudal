# Fase 3 · Patrimonio e inversiones

> **Versión:** `0.6.0` · **Inicio:** 2026-11-03 · **Estado:** 🔄 en curso

## Partes

| Parte | Qué | Estado |
|---|---|---|
| 3.1 | Migración `0004`: `products`, `investment_operations`, `prices`, `manual_valuations` | ✅ |
| 3.2 | `app/prices/`: Yahoo y Morningstar (sin CoinGecko: no hay cripto), caché, histórico y refresco | ⬜ |
| 3.3 | Productos y operaciones: buscador, API, formulario con «duplicar», plantilla y RUMBO | ⬜ |
| 3.4 | Cálculos: FIFO, plusvalías, XIRR, comparativa, TER, aportaciones | ⬜ |
| 3.5 | Pestaña Inversiones | ⬜ |
| 3.6 | Patrimonio con inversiones | ⬜ |
| 3.7 | Cierre | ⬜ |

## Decisiones

- Tipo de producto `commodity` (materia prima) para el oro, que es un ETC y no un ETF.
- `prices.fetched_at`: cuándo se descargó el precio, para avisar de precios desactualizados.
- La lista real de productos de Gerard no se sube a git (el repositorio es público).
