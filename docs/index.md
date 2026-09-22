# Career Copilot — Documentación

Punto de entrada del vault. Todo lo demás cuelga de aquí.

> [!tip] Cómo leer esto
> En Obsidian: abre esta nota y usa el grafo o los backlinks.
> En GitHub: todos los enlaces son relativos, así que funcionan igual en el navegador.

## Qué es

Copiloto local y de un solo usuario para buscar trabajo. Ingesta tu CV, lo audita
contra criterios ATS, agrega vacantes, las puntúa contra tu perfil, adapta el CV a
cada oferta, investiga la empresa y te entrena para la entrevista.

## Mapa

| Nota | Qué responde |
|---|---|
| [Arquitectura](arquitectura.md) | Cómo encajan las piezas y por dónde fluye un dato |
| [Modelo de datos](modelo-de-datos.md) | Qué tablas hay y por qué |
| [API](api.md) | Qué endpoints existen y qué módulo cubre cada uno |
| [Desarrollo](desarrollo.md) | Cómo levantarlo, comandos y variables de entorno |
| [Decisiones (ADR)](adr/index.md) | Por qué está hecho así y no de otra forma |
| [Diario](diario/index.md) | Qué se construyó cada sesión |

## Estado

Los seis módulos están completos de punta a punta: backend, pantalla y —donde
aplica— extensión de navegador. 55 tests pasan sobre la parte determinista
(taxonomía y scoring). Lo que queda es pulido y cobertura, no piezas ausentes.

| Módulo | Backend | Pantalla |
|---|---|---|
| 1 — CV: parsing, ATS, tailoring | Listo | `/cv` — Mi CV |
| 2 — Vacantes: ingesta, matching | Listo | `/vacantes`, `/vacantes/[id]` |
| 3 — Extensión: captura, autofill | Listo | `extension/` (Manifest V3) |
| 4 — Postulaciones: Kanban, tareas | Listo | `/pipeline` |
| 5 — Inteligencia: empresa, salario | Listo | dentro de `/vacantes/[id]` |
| 6 — Entrevistas: simulacro, banco QA | Listo | `/entrevistas` |

Más `/` (Panel) y `/ajustes` (preferencias de búsqueda).

## Pendientes conocidos

Cosas detectadas y aún no resueltas. Cuando una se cierre, se borra de aquí.

- `LLM_FAST_MODEL=claude-haiku-4-5` usa el alias corto; el id completo es
  `claude-haiku-4-5-20251001`. Conviene fijarlo para que la versión no se mueva sola.
- No hay migraciones: el esquema se crea con `Base.metadata.create_all`. Ver
  [ADR 0003](adr/0003-sin-migraciones.md) para cuándo dejaría de valer.
- Los tests cubren solo lo determinista (`test_taxonomy.py`, `test_scoring.py`).
  Las rutas que tocan BD están tras el marcador `needs_db` y no hay tests de los
  servicios que llaman al LLM.
- `backend/smoke_tmp.py` y `backend/ingest_tmp.py` son scripts de prueba manual
  en la raíz de `backend/`. Se dejan a propósito por ahora.
