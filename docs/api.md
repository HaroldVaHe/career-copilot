# API

[← Índice](index.md) · Fuente: `backend/app/api/routes/`

Todo cuelga de `/api/v1`. Con la API levantada tienes la referencia viva y
siempre exacta en **<http://localhost:8000/docs>** (Swagger UI) y
**<http://localhost:8000/redoc>**. Esta nota es el mapa de alto nivel: qué
módulo cubre qué, y las rutas que no son obvias.

## Routers

| Prefijo | Tag | Módulo | Fichero |
|---|---|---|---|
| - | Sistema | Salud y preferencias | `routes/health.py` |
| `/profiles` | Perfiles | Transversal | `routes/profiles.py` |
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
| GET · PUT | `/preferences` | `users.preferences` del perfil activo |

## Perfiles

Cada perfil es una persona: sus CV, postulaciones, simulacros, banco de
respuestas y preferencias. **Todas las rutas** resuelven el perfil con la cabecera
`X-Profile-Id`; sin ella se usa el perfil por defecto (`DEFAULT_USER_EMAIL`), así
que un cliente que no la mande sigue funcionando. Ver
[ADR 0008](adr/0008-multiperfil.md).

| Método | Ruta | Nota |
|---|---|---|
| GET | `/profiles` | Todos, con conteo de CV, postulaciones y mejor ATS |
| GET | `/profiles/current` | El que resuelve la cabecera actual |
| POST | `/profiles` | `{full_name}` |
| PATCH | `/profiles/{id}` | Renombrar |
| DELETE | `/profiles/{id}` | Borra el perfil **y todo lo suyo**. El por defecto no se puede borrar (400) |
| POST | `/profiles/from-resume/{resume_id}` | Mueve un CV del perfil activo a un perfil nuevo con el nombre de su titular. Se lleva variantes, postulaciones y simulacros hechos con él |

Si `X-Profile-Id` apunta a un perfil que no existe, cualquier ruta responde
404 con `code: profile_not_found`; el frontend y la extensión lo usan para
volver al perfil por defecto.

## Módulo 1 - CV

| Método | Ruta | Nota |
|---|---|---|
| POST | `/resumes` | Sube PDF/DOCX/TXT/MD. Extrae, audita y embebe en una llamada |
| GET | `/resumes` | Listado resumido |
| GET · PATCH · DELETE | `/resumes/{id}` | |
| POST | `/resumes/{id}/audit` | Re-audita sin volver a subir |
| GET | `/resumes/{id}/report.pdf` | Informe PDF: puntuación, quick wins, fortalezas, hallazgos, reescrituras, keywords y perfil extraído. `Content-Disposition` con `Informe-CV-<Nombre>.pdf` |
| POST | `/resumes/tailor` | Devuelve la propuesta **como diff**, no la guarda |
| POST | `/resumes/variants` | Guarda la variante que el usuario aceptó |

La separación `tailor` / `variants` es deliberada: el sistema nunca persiste una
reescritura por su cuenta. Ver [ADR 0005](adr/0005-tailoring-con-aprobacion.md).

El PDF se genera en el servidor con reportlab (`services/report_pdf.py`) para
que sea un archivo real e idéntico en cualquier navegador; el frontend lo
descarga o lo pasa al menú nativo de compartir (`navigator.share` con archivo).

## Módulo 2 — Vacantes

| Método | Ruta | Nota |
|---|---|---|
| GET | `/jobs/sources` | Fuentes registradas; `details` trae etiqueta, descripción, si entra por defecto y si filtra por país |
| GET | `/jobs/search-plan?resume_id=` | Qué buscar para un CV: 2-4 títulos de puesto en inglés y país de residencia. `refresh=true` descarta el guardado |
| POST | `/jobs/ingest` | Síncrona. `queries` × `sources`, descarga en paralelo. Con `resume_id` y sin consultas usa el plan del CV; con `country` descarta lo no elegible desde ese país |
| POST | `/jobs` | Alta manual |
| POST | `/jobs/search` | Filtros + ranking semántico. `country` deja solo vacantes elegibles (el país, su región, «worldwide» o sin ubicación) |
| GET | `/jobs/{id}` · DELETE | |
| POST | `/jobs/{id}/analyze` | Re-normaliza con el LLM |
| GET | `/jobs/{id}/match` | Score híbrido (cacheado en `job_matches`) |
| POST | `/jobs/{id}/analysis` | Análisis cualitativo del modelo, bajo demanda |
| POST | `/jobs/reindex` | Recalcula todos los embeddings |

El plan de búsqueda del último import que hizo el usuario para un CV se guarda
en `users.preferences["job_search:<resume_id>"]` y tiene prioridad sobre la
sugerencia de Claude la próxima vez.

## Módulo 3 — Extensión

| Método | Ruta | Nota |
|---|---|---|
| GET | `/capture/ping` | Handshake: devuelve también `user` (nombre) y `profile_id` del perfil resuelto |
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

## Errores globales

`main.py` registra manejadores globales, así que ninguna ruta los repite:

| Excepción | HTTP | `code` |
|---|---|---|
| `LLMUnavailable` (sin API key) | 503 | `llm_unavailable` |
| `LLMError` (fallo de la llamada) | 502 | `llm_error` |
| `ProfileNotFound` (`X-Profile-Id` inexistente) | 404 | `profile_not_found` |
