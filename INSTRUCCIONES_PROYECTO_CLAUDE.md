# Cómo montar el proyecto "Caudal" en Claude

Guía para Gerard: crear el proyecto en Claude una vez y empezar cada fase en un chat nuevo.

---

## 1. Crear el proyecto

1. En Claude: **Proyectos → Nuevo proyecto**.
2. **Nombre:** `Caudal`
3. **Descripción:** `App local de finanzas personales y familiares: patrimonio, movimientos e inversiones.`

## 2. Subir los archivos al conocimiento del proyecto

| Archivo | Para qué |
|---|---|
| `CLAUDE.md` | **Cómo debe trabajar Claude** cada fase, de la 0 al final |
| `docs/DISENO.md` | **Fuente de verdad**: decisiones, formatos, modelo de datos y roadmap |
| `README.md` | Presentación del proyecto y estado del roadmap |
| `CHANGELOG.md` | En qué punto está el proyecto |
| `maqueta/caudal-maqueta.html` | Diseño de referencia (Claude puede leer su código) |

Las capturas de `docs/capturas/` y este archivo no hace falta subirlos.

> **Nunca subas extractos reales** al proyecto. Solo ejemplos con datos inventados.

## 3. Pegar las instrucciones del proyecto

En el proyecto, abre **Instrucciones** y pega esto tal cual:

```text
Proyecto: Caudal, app local de finanzas personales y familiares (patrimonio, movimientos e inversiones).

Al empezar cada conversación:
1. Lee CLAUDE.md y sigue su protocolo (sección 4) y el detalle de la fase que toque (sección 7).
2. Lee docs/DISENO.md: es la fuente de verdad de las decisiones. Si lo que te pido lo contradice, avísame y propón el cambio del documento antes de seguir.
3. Mira CHANGELOG.md para saber en qué punto está el proyecto y pídeme lo que te falte (git log, archivos concretos, ejemplos inventados).

Siempre:
- En español. Paso a paso, con archivos completos y comandos exactos para Mac (zsh) y, cuando cambien, también para PowerShell.
- Sigue el diseño de maqueta/caudal-maqueta.html.
- No inventes formatos de bancos o brokers ni funciones de librerías. Si no sabes algo, dilo.
- Nunca me pidas datos reales ni secretos; si te pego alguno, avísame y no lo reutilices.
- Sé honesto con los riesgos y las alternativas.
- Al acabar la fase: repasa los criterios de "hecho", dame las actualizaciones de CHANGELOG.md, README.md (y DISENO.md si cambió algo), el mensaje de commit y el mensaje para empezar la siguiente fase.
```

## 4. Empezar cada fase

Abre un **chat nuevo dentro del proyecto** y escribe el mensaje de la fase. Claude ya sabe qué hacer gracias a `CLAUDE.md`.

| Fase | Mensaje | Adjuntar |
|---|---|---|
| 0 | `Empezamos la Fase 0 de Caudal. Sigue CLAUDE.md.` | — |
| 1a | `Empezamos la Fase 1a de Caudal (base + inicio de sesión). Sigue CLAUDE.md.` | — |
| 1b | `Empezamos la Fase 1b de Caudal (importadores imagin + Wise). Te adjunto los ejemplos inventados. Sigue CLAUDE.md.` | `samples/imagin_ejemplo.xlsx`, `samples/wise_ejemplo.xlsx` |
| 1c | `Empezamos la Fase 1c de Caudal (categorización + pestañas). Sigue CLAUDE.md.` | — |
| 1d | `Empezamos la Fase 1d de Caudal (backups + accesos directos). Sigue CLAUDE.md.` | — |
| 2 | `Empezamos la Fase 2 de Caudal (control del gasto). Sigue CLAUDE.md.` | — |
| 3 | `Empezamos la Fase 3 de Caudal (patrimonio e inversiones). Te adjunto los ejemplos inventados que tenga. Sigue CLAUDE.md.` | Ejemplos de Trade Republic / Scalable |
| 4 | `Empezamos la Fase 4 de Caudal (los padres). Te adjunto los ejemplos inventados. Sigue CLAUDE.md.` | Ejemplos de CaixaBank / Sabadell |
| 5 | `Empezamos la Fase 5 de Caudal. Repasa los extras y ayúdame a priorizar. Sigue CLAUDE.md.` | — |
| 6 | `Empezamos la Fase 6 de Caudal (migración a Mac). Sigue CLAUDE.md.` | — |
| 7 | `Empezamos la Fase 7 de Caudal (versión demo para el CV). Sigue CLAUDE.md.` | — |

**Si una fase se alarga**, puedes seguir en otro chat: `Seguimos con la Fase X de Caudal. Lo último que hicimos fue …`

## 5. Al cerrar cada fase

1. Aplica en tu carpeta los cambios de `CHANGELOG.md`, `README.md` (y `docs/DISENO.md` si cambió).
2. Haz el commit con el mensaje que te dé Claude.
3. En el conocimiento del proyecto, **sustituye** los archivos que hayan cambiado por la versión nueva. No dejes dos versiones del mismo archivo.

## 6. Dónde vive cada cosa

- **El código** está en tus ordenadores (`~/Proyectos/caudal`) con Git, y en tu GitHub.
- **En Claude** quedan las conversaciones y los documentos del proyecto. Mantenlos al día.
