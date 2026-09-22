# API

[← Índice](index.md) · Fuente: `backend/app/api/routes/`

Todo cuelga de `/api/v1`. Con la API levantada tienes la referencia viva y
siempre exacta en **<http://localhost:8000/docs>** (Swagger UI) y
**<http://localhost:8000/redoc>**. Esta nota es el mapa de alto nivel: qué
módulo cubre qué, y las rutas que no son obvias.

## Routers

| Prefijo | Tag | Módulo | Fichero |
|---|---|---|---|
| — | Sistema | Salud y preferencias | `routes/health.py` |
| `/resumes` | CV | Módulo 1 | `routes/resumes.py` |
| `/jobs` | Vacantes | Módulo 2 | `routes/jobs.py` |
| `/capture` | Extensión | Módulo 3 | `routes/capture.py` |
| `/applications` | Postulaciones | Módulo 4 | `routes/applications.py` |
| `/intel` | Inteligencia | Módulo 5 | `routes/intel.py` |
| `/interview` | Entrevistas | Módulo 6 | `routes/interview.py` |

## Sistema

| Método | Ruta | Nota |
|---|---|---|
| GET | `/health` | Estado de BD, LLM y fuentes disponibles |
| GET | `/stats` | Conteos de CV, vacantes y postulaciones |
| GET · PUT | `/preferences` | `users.preferences` |

## Módulo 1 — CV

| Método | Ruta | Nota |
|---|---|---|
| POST | `/resumes` | Sube PDF/DOCX/TXT/MD. Extrae, audita y embebe en una llamada |
| GET | `/resumes` | Listado resumido |
| GET · PATCH · DELETE | `/resumes/{id}` | |
| POST | `/resumes/{id}/audit` | Re-audita sin volver a subir |
| POST | `/resumes/tailor` | Devuelve la propuesta **como diff**, no la guarda |
| POST | `/resumes/variants` | Guarda la variante que el usuario aceptó |

La separación `tailor` / `variants` es deliberada: el sistema nunca persiste una
reescritura por su cuenta. Ver [ADR 0005](adr/0005-tailoring-con-aprobacion.md).

## Módulo 2 — Vacantes

| Método | Ruta | Nota |
|---|---|---|
| GET | `/jobs/sources` | Fuentes públicas registradas |
| POST | `/jobs/ingest` | Ingesta en background |
| POST | `/jobs` | Alta manual |
| POST | `/jobs/search` | Filtros + ranking semántico |
| GET | `/jobs/{id}` · DELETE | |
| POST | `/jobs/{id}/analyze` | Re-normaliza con el LLM |
| GET | `/jobs/{id}/match` | Score híbrido (cacheado en `job_matches`) |
| POST | `/jobs/{id}/analysis` | Análisis cualitativo del modelo, bajo demanda |
| POST | `/jobs/reindex` | Recalcula todos los embeddings |

## Módulo 3 — Extensión

| Método | Ruta | Nota |
|---|---|---|
| GET | `/capture/ping` | Handshake para que la extensión detecte el backend |
| POST | `/capture` | Recibe el HTML de la oferta abierta y la normaliza |
| GET | `/capture/autofill` | Perfil para rellenar formularios de aplicación |
| POST | `/capture/answer` | Responde una pregunta abierta del formulario usando CV + banco QA |

CORS: `main.py` acepta `chrome-extension://*` y `moz-extension://*` por regex,
porque el id de la extensión no se puede listar de antemano.

## Módulo 4 — Postulaciones

| Método | Ruta | Nota |
|---|---|---|
| GET | `/applications/board` | Kanban ya agrupado por columna |
| GET · POST | `/applications` | |
| GET · PATCH · DELETE | `/applications/{id}` | |
| POST | `/applications/{id}/tasks` | Alta manual |
| POST | `/applications/{id}/tasks/generate` | Checklist generado por el modelo |
| PATCH · DELETE | `/applications/tasks/{task_id}` | |
| GET · POST | `/applications/{id}/events` | Timeline |
| POST | `/applications/{id}/cover-letter` | |

## Módulo 5 — Inteligencia

| Método | Ruta | Nota |
|---|---|---|
| GET | `/intel/company` | Por nombre de empresa |
| GET | `/intel/jobs/{id}/company` | |
| GET | `/intel/jobs/{id}/interview` | Etapas, tipo de prueba, preguntas frecuentes |
| GET | `/intel/jobs/{id}/salary` | Benchmark |
| GET | `/intel/jobs/{id}/brief` | Dossier completo: empresa + proceso + salario + match |

Todo lo que sale de búsqueda web llega con `sources` y `confidence`.

## Módulo 6 — Entrevistas

| Método | Ruta | Nota |
|---|---|---|
| POST | `/interview/sessions` | Arranca el simulacro (máx. 8 preguntas) |
| GET | `/interview/sessions` · `/{id}` | |
| POST | `/interview/sessions/{id}/answer` | Respuesta + feedback inmediato |
| POST | `/interview/sessions/{id}/finish` | Resumen final |
| DELETE | `/interview/sessions/{id}` | |
| GET · POST | `/interview/qa` | Banco personal de respuestas |
| PATCH · DELETE | `/interview/qa/{id}` | |

## Errores del LLM

`main.py` registra dos manejadores globales, así que ninguna ruta los repite:

| Excepción | HTTP | `code` |
|---|---|---|
| `LLMUnavailable` (sin API key) | 503 | `llm_unavailable` |
| `LLMError` (fallo de la llamada) | 502 | `llm_error` |
