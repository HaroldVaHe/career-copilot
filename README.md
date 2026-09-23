# Career Copilot

Copiloto local de búsqueda de empleo. Ingesta tu CV, lo audita contra criterios
ATS, agrega vacantes, las puntúa contra tu perfil, adapta el CV a cada oferta,
investiga la empresa y te entrena para la entrevista.

Corre entero en tu máquina: un perfil por persona, sin cuentas, sin nada en la nube
salvo las llamadas a la API de Claude.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | FastAPI · SQLAlchemy 2 · Pydantic 2 |
| Datos | Postgres 16 + pgvector + pg_trgm · Redis 7 |
| IA | Claude (Anthropic) · embeddings locales o Voyage |
| Frontend | Next.js 16 · React 19 · Tailwind 4 |
| Extensión | Chrome Manifest V3 (`extension/`, sin empaquetar) |

## Arranque rápido

```bash
docker compose up -d
cp .env.example .env          # rellena ANTHROPIC_API_KEY

cd backend
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --reload-dir app --timeout-graceful-shutdown 3 --port 8000
```

API en <http://localhost:8000> · Swagger en <http://localhost:8000/docs>

Sin `ANTHROPIC_API_KEY` arranca igual, en modo degradado. Pasos completos y
variables de entorno en [docs/desarrollo.md](docs/desarrollo.md).

## Módulos

Los seis están completos de punta a punta (backend + pantalla):

1. **CV** — parsing a JSON, auditoría ATS 0-100, informe PDF para compartir, tailoring con diff, versionado. → `/cv`
2. **Vacantes** — búsqueda global según el CV (puestos y país), filtros y matching semántico. → `/vacantes`
3. **Extensión** — captura de ofertas desde el navegador, autofill y selector de perfil. → `extension/`
4. **Postulaciones** — Kanban, checklist generado por IA, timeline, cover letters. → `/pipeline`
5. **Inteligencia** — empresa, proceso de entrevista y benchmark salarial. → dossier de la vacante
6. **Entrevistas** — simulacro con feedback y banco de respuestas reutilizables. → `/entrevistas`

Además, **perfiles**: varias personas en la misma instalación, cada una con sus
CV, pipeline y entrevistas. → `/perfiles` y selector en la barra lateral.

87 tests pasando (parte determinista, PDF, geografía de vacantes y perfiles).

## Documentación

La carpeta [`docs/`](docs/index.md) es a la vez un **vault de Obsidian** y
markdown normal: se lee igual abriendo el repo en Obsidian que navegándolo en
GitHub.

| Nota | Contenido |
|---|---|
| [Índice](docs/index.md) | Mapa y estado del proyecto |
| [Arquitectura](docs/arquitectura.md) | Capas, flujos y diagramas |
| [Modelo de datos](docs/modelo-de-datos.md) | Las 12 tablas y por qué |
| [API](docs/api.md) | Mapa de endpoints por módulo |
| [Desarrollo](docs/desarrollo.md) | Setup, comandos, variables |
| [Decisiones (ADR)](docs/adr/index.md) | Por qué está hecho así |
| [Diario](docs/diario/index.md) | Qué se construyó cada sesión |

Para abrirlo en Obsidian: *Abrir carpeta como vault* → la raíz del repo. La
configuración de `.obsidian/` ya viene versionada.

## Estructura

```
career-copilot/
├── backend/app/
│   ├── api/routes/     # HTTP: 7 routers bajo /api/v1
│   ├── services/       # Lógica de negocio (sin FastAPI)
│   ├── models/         # SQLAlchemy
│   ├── schemas/        # Pydantic: contrato de API y de LLM
│   └── db/             # Sesión e inicialización
├── frontend/src/
│   ├── app/            # App Router: panel, cv, vacantes, pipeline, entrevistas
│   ├── components/     # Kit de UI, gráficos, nav, diff
│   └── lib/            # Cliente de API tipado y tipos espejo de Pydantic
├── extension/          # Chrome Manifest V3: popup, extractores, autofill
├── infra/db/           # init.sql (extensiones)
└── docs/               # Vault de Obsidian
```

## Licencia

Proyecto personal.
