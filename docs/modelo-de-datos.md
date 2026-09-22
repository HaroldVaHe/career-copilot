# Modelo de datos

[← Índice](index.md) · Fuente: `backend/app/models/entities.py`

Todo vive en Postgres. Tres tipos de columna con propósitos distintos:

- **Escalares** — lo que se filtra y se ordena en SQL.
- **`JSONB`** — las estructuras que produce el LLM. Evolucionan rápido y no quiero
  una migración cada vez que un esquema Pydantic gana un campo. Cada columna
  `JSONB` tiene un modelo Pydantic espejo en `app/schemas/`.
- **`Vector(EMBEDDING_DIM)`** — búsqueda semántica vía pgvector.

```mermaid
erDiagram
    User ||--o{ Resume : tiene
    User ||--o{ Application : tiene
    User ||--o{ InterviewSession : realiza
    User ||--o{ QAEntry : guarda
    Job  ||--o{ Application : origina
    Resume ||--o{ JobMatch : puntua
    Job  ||--o{ JobMatch : puntua
    Resume ||--o{ Resume : "variante de"
    Application ||--o{ ApplicationEvent : registra
    Application ||--o{ Task : contiene
```

## Tablas

| Tabla | Para qué | Campos que conviene conocer |
|---|---|---|
| `users` | Perfil local único | `preferences` (JSONB): roles objetivo, salario, países |
| `resumes` | CV y sus variantes | `parsed`, `ats_report`, `ats_score`, `embedding`, `parent_id`, `tailored_for_job_id` |
| `jobs` | Vacantes normalizadas | `requirements` (JSONB), `embedding`, único por `(source, external_id)` |
| `job_matches` | Match cacheado CV×vacante | `score` y sus tres componentes, `matched_skills`, `missing_skills`, `analysis` |
| `applications` | CRM / Kanban | `status`, `board_order`, `cover_letter`, `next_action_at`; único por `(user_id, job_id)` |
| `application_events` | Timeline | `kind`, `payload` (JSONB) |
| `tasks` | Checklist por postulación | `category`, `done`, `due_at`, `order_index` |
| `company_intel` | Investigación cacheada | único por `company_key`, con `refreshed_at` para expirar |
| `interview_insights` | Cómo entrevista una empresa | único por `(company_key, role_key)` |
| `interview_sessions` | Simulacros | `transcript` (JSONB), `summary`, `finished` |
| `qa_entries` | Banco personal de respuestas | `embedding` para recuperar la respuesta parecida |

## Detalles que no se ven en el diagrama

**Variantes de CV.** Un CV adaptado a una oferta es otra fila en `resumes`, con
`parent_id` apuntando al original y `tailored_for_job_id` a la vacante. Nunca se
sobrescribe el CV base. Ver [ADR 0005](adr/0005-tailoring-con-aprobacion.md).

**Estados del Kanban.** `ApplicationStatus` define el orden del tablero: `saved →
applied → recruiter_contact → technical_test → final_interview → offer`, más
`rejected` y `withdrawn` fuera del flujo. `ACTIVE_STATUSES` excluye esos dos.

**Dimensión del embedding.** `EMB_DIM` se lee de `settings.embedding_dim` **en
tiempo de import**. Cambiar `EMBEDDING_DIM` en el `.env` con datos ya guardados
rompe las columnas `Vector`: hay que recrear las tablas y reindexar
(`POST /api/v1/jobs/reindex`). Ver [ADR 0002](adr/0002-embeddings.md).

**Creación del esquema.** No hay Alembic. `app/db/init_db.py` crea extensiones
(`vector`, `pg_trgm`), tablas y el usuario local en el arranque. Ver
[ADR 0003](adr/0003-sin-migraciones.md).
