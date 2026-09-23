# Career Copilot — contexto para Claude Code

Herramienta local de búsqueda de empleo. Varios perfiles (uno por persona, elegido
con la cabecera `X-Profile-Id`, ver ADR 0008), sin autenticación,
todo en `localhost`. FastAPI + Postgres/pgvector + Claude, frontend Next.js.

Antes de trabajar, lee [docs/index.md](docs/index.md) y, si la tarea toca una
zona con decisión tomada, el ADR correspondiente en [docs/adr/](docs/adr/index.md).

## Documentar es parte de la tarea, no un paso aparte

Al terminar cualquier cambio, actualiza lo que haya quedado desfasado **en el
mismo turno**, sin esperar a que te lo pidan:

| Si el cambio... | Actualiza |
|---|---|
| Añade o cambia un endpoint | [docs/api.md](docs/api.md) |
| Toca `models/entities.py` | [docs/modelo-de-datos.md](docs/modelo-de-datos.md) |
| Cambia cómo encajan las piezas o un flujo | [docs/arquitectura.md](docs/arquitectura.md) |
| Añade dependencia, comando o variable de entorno | [docs/desarrollo.md](docs/desarrollo.md) y `.env.example` |
| Toma una decisión estructural o cara de revertir | ADR nuevo en [docs/adr/](docs/adr/index.md) + fila en su índice |
| Completa o desbloquea un módulo | Tabla de estado en [docs/index.md](docs/index.md) |

Al cerrar una sesión de trabajo con avance real, añade una entrada en
[docs/diario/](docs/diario/index.md) usando `docs/_templates/diario.md`.

Si detectas algo desfasado o a medias que no toca arreglar ahora, anótalo en
«Pendientes conocidos» de `docs/index.md` en vez de dejarlo sin registro.

## Reglas de las notas

- **Enlaces markdown relativos, nunca `[[wikilinks]]`.** El vault se lee también
  desde GitHub y los wikilinks no renderizan allí.
- Diagramas en `mermaid` — lo renderizan Obsidian y GitHub.
- Nada de Dataview ni plugins de comunidad: rompen la lectura en el navegador.
- Un ADR no se reescribe al cambiar de opinión: se marca `Reemplazado por` y se
  crea uno nuevo.
- Documenta el **porqué**. El qué ya está en el código y en `/docs` de Swagger.

## Convenciones de código

- Los servicios (`app/services/`) no importan `fastapi`. La lógica no sabe que
  existe HTTP; las rutas solo validan, delegan y serializan.
- Toda llamada al modelo pasa por `app/services/llm.py`, con salida estructurada
  vía JSON Schema derivado de Pydantic. Ver [ADR 0006](docs/adr/0006-salida-estructurada-llm.md).
- Cada columna `JSONB` tiene su modelo Pydantic espejo en `app/schemas/`.
- Los errores del LLM se manejan globalmente en `main.py` (503/502). No repitas
  ese `try/except` en las rutas.
- Nuevas dependencias de acceso a datos van en `app/api/deps.py`.
- Docstrings de módulo que expliquen la intención, en español, como los actuales.

## Cosas que romperías sin saberlo

- **`EMBEDDING_DIM`** define el tipo de las columnas `Vector` en tiempo de
  import. Cambiarlo invalida todo lo guardado: hay que recrear tablas y llamar a
  `POST /api/v1/jobs/reindex`.
- **No hay migraciones.** `create_all` no altera tablas existentes: un cambio de
  columna exige `docker compose down -v`. Ver [ADR 0003](docs/adr/0003-sin-migraciones.md).
- **El tailoring nunca guarda solo.** `POST /resumes/tailor` propone un diff;
  solo `POST /resumes/variants` persiste. Ver [ADR 0005](docs/adr/0005-tailoring-con-aprobacion.md).
- **No añadas scraping** de LinkedIn, Indeed, Glassdoor, Workday, Greenhouse,
  Lever o Taleo. Esa vía es la extensión. Ver [ADR 0004](docs/adr/0004-extension-en-vez-de-scraping.md).
- **Todo lo personal se filtra por el perfil activo.** Una ruta nueva que lea CV,
  postulaciones, simulacros o respuestas debe depender de `CurrentUser` y filtrar
  por `user.id`; si no, mezcla datos entre personas. `jobs` e intel son compartidos.
  Ver [ADR 0008](docs/adr/0008-multiperfil.md).
- **El sistema debe arrancar sin `ANTHROPIC_API_KEY`**, en modo degradado. No
  introduzcas dependencias duras del LLM en el camino de arranque.

## Comandos

```bash
docker compose up -d                                    # Postgres + Redis
cd backend && uvicorn app.main:app --reload --reload-dir app --timeout-graceful-shutdown 3 --port 8000 # API
cd frontend && npm run dev                              # Frontend
cd backend && pytest                                    # Tests (87)
```
