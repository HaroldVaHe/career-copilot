# Arquitectura

[← Índice](index.md)

## Vista general

```mermaid
graph TD
    FE["Frontend<br/>Next.js 16 · React 19 · Tailwind 4"]
    EXT["Extensión de navegador<br/>Manifest V3 · extension/"]
    API["FastAPI<br/>/api/v1"]
    SVC["Capa de servicios<br/>backend/app/services"]
    PG[("Postgres 16<br/>+ pgvector + pg_trgm")]
    RD[("Redis 7")]
    CL["API de Claude"]
    SRC["Fuentes públicas<br/>de vacantes"]

    FE -->|REST| API
    EXT -->|POST /capture| API
    API --> SVC
    SVC --> PG
    SVC --> RD
    SVC --> CL
    SVC --> SRC
```

## Capas

El backend es una cebolla de cuatro capas y la regla es que nunca se salta hacia
atrás: una ruta no habla con la base de datos sin pasar por un servicio, y un
servicio no conoce FastAPI.

| Capa | Carpeta | Responsabilidad |
|---|---|---|
| Rutas | `app/api/routes/` | HTTP: validar entrada, elegir códigos de estado, serializar |
| Servicios | `app/services/` | Toda la lógica de negocio. No importa nada de `fastapi` |
| Modelos | `app/models/` | Tablas SQLAlchemy. Ver [Modelo de datos](modelo-de-datos.md) |
| Esquemas | `app/schemas/` | Pydantic: contrato de la API y contrato de salida del LLM |

`app/api/deps.py` concentra las dependencias compartidas (sesión de BD, usuario
actual, resolución de `job_id`/`resume_id`/`application_id` con 404 automático).

## La decisión que explica casi todo

Cada capacidad se resuelve con la mezcla más barata que dé el resultado correcto:
lo determinista en Python, lo que exige criterio en Claude.

| Capacidad | Parte determinista | Parte del modelo |
|---|---|---|
| Auditoría ATS | Formato, densidad de keywords, secciones ausentes | Si un bullet realmente vende |
| Matching | Cobertura de skills (taxonomía), distancia de seniority | Análisis cualitativo bajo demanda |
| Vacantes | Deduplicación, parseo de fechas | Normalización del texto libre a JSON |
| Intel | Cacheo y expiración | Búsqueda web con `sources` y `confidence` |

Consecuencia práctica: **sin `ANTHROPIC_API_KEY` el sistema arranca igual**, en
modo degradado (parsing heurístico, matching por taxonomía, sin tailoring ni
intel ni simulacros). `main.py` lo avisa con un warning en el arranque.

## Flujo 1 — Del CV al informe ATS

```mermaid
sequenceDiagram
    participant U as Usuario
    participant R as routes/resumes.py
    participant D as services/documents.py
    participant S as services/resume.py
    participant A as services/ats.py
    participant E as services/embeddings.py
    participant DB as Postgres

    U->>R: POST /resumes (PDF/DOCX)
    R->>D: parse_document()
    D-->>R: texto + DocumentSignals (tablas, columnas, imágenes)
    R->>S: extracción estructurada
    S->>S: Claude → ResumeData (JSON Schema)
    R->>A: auditoría
    A->>A: reglas deterministas + revisión del modelo
    A-->>R: AtsReport (0-100)
    R->>E: embed(texto)
    R->>DB: Resume{parsed, ats_report, embedding}
```

`DocumentSignals` existe porque hay penalizaciones de ATS que solo se ven mirando
el archivo, no el texto ya extraído: tablas, multi-columna, imágenes, fuentes raras.

## Flujo 2 — De la vacante al match

```mermaid
sequenceDiagram
    participant J as routes/jobs.py
    participant SR as services/sources/
    participant N as services/jobs.py
    participant M as services/matching.py
    participant DB as Postgres

    J->>SR: POST /jobs/ingest
    SR-->>J: RawJob[] (fuentes públicas, sin API key)
    J->>N: normalizar
    N->>N: LLM_FAST_MODEL → JobNormalized + JobRequirements
    N->>DB: upsert por (source, external_id)
    J->>M: GET /jobs/{id}/match
    M->>M: 0.50 skills + 0.35 semántico + 0.15 seniority
    M->>DB: JobMatch cacheado
```

El score no es coseno puro. Un reclutador filtra por skills duras antes que por
parecido general, así que la cobertura de requisitos pesa más y la similitud
semántica actúa de desempate. Pesos en `services/matching.py:WEIGHTS`.

## Por qué hay una extensión y no un scraper

LinkedIn, Indeed, Glassdoor, Workday, Greenhouse, Lever y Taleo prohíben el
scraping en sus términos y banean cuentas. La extensión lee la página que el
usuario **ya tiene abierta en su propia sesión** y la envía a `/api/v1/capture`.
Las fuentes de `services/sources/` son solo las que ofrecen API pública sin key.

La extensión vive en `extension/` (Manifest V3): un `popup` para capturar y ver
el match, `extractors.js` con un extractor por portal, y `autofill.js` para
rellenar formularios. Sus `host_permissions` apuntan solo a `localhost:8000`.

Detalle en [ADR 0004](adr/0004-extension-en-vez-de-scraping.md).

## Frontend

Next.js con App Router. `src/lib/api.ts` es el único punto que habla con el
backend y `src/lib/types.ts` refleja los esquemas Pydantic, así que un cambio de
contrato se ve en un solo sitio.

| Ruta | Pantalla |
|---|---|
| `/` | Panel |
| `/cv` | Mi CV: subida, informe ATS, diff de tailoring |
| `/vacantes` · `/vacantes/[id]` | Listado con filtros · dossier e intel |
| `/pipeline` | Kanban de postulaciones |
| `/entrevistas` | Simulacro y banco de respuestas |
| `/ajustes` | Preferencias de búsqueda |

## Notas relacionadas

- [Modelo de datos](modelo-de-datos.md)
- [API](api.md)
- [Decisiones](adr/index.md)
