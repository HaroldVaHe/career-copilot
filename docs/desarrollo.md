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
uvicorn app.main:app --reload --reload-dir app --timeout-graceful-shutdown 3 --port 8000

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
perfil por defecto en el arranque de la API.

### Si `--reload` no recoge los cambios

Pasó en Windows con el repo en otra unidad (`F:`). Tres causas, tres flags:

| Síntoma | Causa | Arreglo |
|---|---|---|
| Recarga al instalar paquetes y se cuelga | Vigila también `.venv/` | `--reload-dir app` |
| Detecta el cambio pero sigue sirviendo el código viejo | El proceso viejo espera a que el navegador suelte sus conexiones keep-alive | `--timeout-graceful-shutdown 3` |
| No detecta nada | Los eventos del sistema de archivos no llegan | `$env:WATCHFILES_FORCE_POLLING="true"` antes de arrancar |

Si el puerto 8000 sigue ocupado tras matar uvicorn, queda un hijo de
`multiprocessing` con el socket heredado: búscalo con
`Get-CimInstance Win32_Process -Filter "Name='python.exe'"` y mátalo.

## Extensión de navegador

No está publicada: se carga sin empaquetar.

1. `chrome://extensions` → activa **Modo de desarrollador**.
2. **Cargar descomprimida** → selecciona la carpeta `extension/`.
3. Con la API levantada, abre una oferta y pulsa el icono.

Sus `host_permissions` apuntan solo a `localhost:8000`, así que si cambias
`API_PORT` hay que actualizar `extension/manifest.json`.

Tras actualizarla, pulsa **Recargar** en `chrome://extensions` (la versión sube
en `manifest.json`). Con dos o más perfiles, el popup muestra un selector de
perfil; se guarda en `chrome.storage.sync`, aparte del perfil activo del dashboard.

## Tests

```bash
cd backend
.venv/Scripts/python -m pytest -q     # Windows
# .venv/bin/python -m pytest -q       # macOS / Linux
```

87 tests: taxonomía, scoring, matching, geografía de vacantes (`test_geo.py`),
informe PDF y plan de búsqueda (`test_report_pdf.py`) y aislamiento de perfiles
(`test_profiles.py`). Los que necesitan Postgres están tras el marcador
`needs_db` de `tests/conftest.py` y se saltan solos si la base no está arriba -
así la suite corre sin Docker. Los de perfiles crean y borran un perfil temporal.

## Dependencias con motivo

| Paquete | Para qué |
|---|---|
| `reportlab` | Informe PDF del CV. Python puro: sin GTK ni binarios del sistema, a diferencia de WeasyPrint |

## Variables de entorno

Referencia completa y comentada en `.env.example`. Las que más se tocan:

| Variable | Default | Nota |
|---|---|---|
| `ANTHROPIC_API_KEY` | vacío | Sin ella el sistema arranca en modo degradado |
| `LLM_MODEL` | `claude-opus-5-5` | `claude-sonnet-5` si haces muchas llamadas |
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
