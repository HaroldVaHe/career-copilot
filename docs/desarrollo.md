# Desarrollo

[← Índice](index.md)

## Requisitos

Docker (Postgres + Redis), Python 3.12+ y Node 20+.

## Arranque

```bash
# 1. Infraestructura. Puertos desplazados a 5433/6380 para no chocar
#    con instalaciones locales de Postgres/Redis.
docker compose up -d

# 2. Configuración
cp .env.example .env      # y rellena ANTHROPIC_API_KEY

# 3. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 4. Frontend (otra terminal)
cd frontend
npm install
npm run dev
```

| Servicio | URL |
|---|---|
| API | <http://localhost:8000> |
| Swagger | <http://localhost:8000/docs> |
| ReDoc | <http://localhost:8000/redoc> |
| Salud | <http://localhost:8000/api/v1/health> |
| Frontend | <http://localhost:3000> |
| Postgres | `localhost:5433` — `copilot` / `copilot` / `career_copilot` |
| Redis | `localhost:6380` |

No hay paso de migración: `app/db/init_db.py` crea extensiones, tablas y el
usuario local en el arranque de la API.

## Variables de entorno

Referencia completa y comentada en `.env.example`. Las que más se tocan:

| Variable | Default | Nota |
|---|---|---|
| `ANTHROPIC_API_KEY` | vacío | Sin ella el sistema arranca en modo degradado |
| `LLM_MODEL` | `claude-opus-5` | `claude-sonnet-5` si haces muchas llamadas |
| `LLM_FAST_MODEL` | `claude-haiku-4-5` | Normalización de vacantes scrapeadas |
| `LLM_EFFORT` | `high` | `low`…`max`: profundidad de razonamiento y costo |
| `EMBEDDING_PROVIDER` | `local` | `local` \| `voyage` — ver [ADR 0002](adr/0002-embeddings.md) |
| `EMBEDDING_DIM` | `512` | Cambiarlo obliga a recrear tablas y reindexar |
| `DATABASE_URL` | `…@localhost:5433/career_copilot` | Debe coincidir con `docker-compose.yml` |
| `CORS_ORIGINS` | `http://localhost:3000` | La extensión entra por regex, no por esta lista |

## Modo degradado

Sin `ANTHROPIC_API_KEY` el arranque avisa y sigue. Qué funciona y qué no:

| Funciona | No funciona |
|---|---|
| Subir CV (parsing heurístico) | Extracción estructurada de calidad |
| Reglas deterministas del ATS | Revisión cualitativa del ATS |
| Matching por taxonomía y embeddings locales | Análisis cualitativo del match |
| CRM, Kanban, tareas manuales | Tailoring, cover letters, intel, simulacros |

## Trabajar con el vault

El vault de Obsidian **es el repositorio**: abre Obsidian → *Abrir carpeta como
vault* → `career-copilot`. La configuración versionada en `.obsidian/` ya fuerza
enlaces markdown relativos, así que todo lo que escribas se sigue viendo bien en
GitHub. No uses `[[wikilinks]]`: GitHub no los renderiza.

Plantillas en `docs/_templates/` (ctrl+P → *Insert template*):

- `adr.md` — una decisión de arquitectura
- `diario.md` — una entrada de sesión

## Convenciones de código

- Servicios sin `fastapi` importado. La lógica no sabe que existe HTTP.
- Toda llamada al modelo pasa por `app/services/llm.py`, siempre con salida
  estructurada (`output_config.format` + JSON Schema derivado de Pydantic).
- Cada columna `JSONB` tiene su modelo Pydantic espejo en `app/schemas/`.
- Docstrings de módulo que explican el *porqué*, no el *qué*.

## Notas relacionadas

- [Arquitectura](arquitectura.md) · [API](api.md) · [Modelo de datos](modelo-de-datos.md)
