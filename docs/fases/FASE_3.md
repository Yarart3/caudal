# Fase 3 · Patrimonio e inversiones

> **Versión:** `0.6.0` · **Inicio:** 2026-11-03 · **Estado:** 🔄 en curso

## Partes

| Parte | Qué | Estado |
|---|---|---|
| 3.1 | Migración `0004`: `products`, `investment_operations`, `prices`, `manual_valuations` | ✅ |
| 3.2a | `app/prices/yahoo.py`: precio, histórico y búsqueda por ISIN, y el comando `python -m app.prices` | ✅ |
| 3.2b | Migración `0005` (`exchange_rates`) y servicio de precios: histórico, divisas y aviso de precio desactualizado | ✅ |
| 3.2c | Refresco automático (al abrir y cada `PRICE_REFRESH_MIN`) y `GET /api/prices/status` · `POST /api/prices/refresh` | ✅ |
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
- Buscar por ISIN en Yahoo da una sola cotización (Londres o Milán), no la de Xetra: el formulario de productos (3.3) dejará escribir el símbolo y enseñará su precio y divisa antes de guardar.
- Tipos de cambio en su propia tabla (`exchange_rates`), sin usuario: son datos públicos. Símbolo `{DIVISA}EUR=X`; los precios en peniques (`GBp`/`GBX`) se guardan en libras.
- Precio desactualizado: se mira **cuándo se descargó** (`fetched_at`), no la fecha del precio. El sábado, el precio del viernes bajado hoy no está desactualizado.
- Un símbolo que tengan varios usuarios se descarga una sola vez.
- Commits como en las fases 1 y 2, con la fase al final: `… (phase 3, step 3.2c)` (petición de Gerard).
- Refresco: al arrancar solo si algún precio falta o es antiguo; luego cada `PRICE_REFRESH_MIN` siempre (una petición por símbolo y divisa). Dos refrescos no se pisan.
- `POST /api/prices/refresh` actualiza solo los productos del usuario. `PRICE_AUTO=false` apaga el refresco automático (los tests lo apagan: nunca salen a internet).
