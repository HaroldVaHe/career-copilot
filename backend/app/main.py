"""Career Copilot — API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.init_db import init_db
from app.services.llm import LLMError, LLMUnavailable

log = get_logger(__name__)

DESCRIPTION = """
Copiloto de postulación y optimización de carrera.

* **CV** — parsing a JSON, auditoría ATS con puntuación 0-100, diff de mejoras y versionado.
* **Vacantes** — agregación desde fuentes públicas, filtros avanzados y matching semántico.
* **Postulaciones** — Kanban, checklist generado por IA, timeline y cartas de presentación.
* **Inteligencia** — investigación de empresa, proceso de entrevista y benchmark salarial.
* **Entrevistas** — simulacro con feedback inmediato y banco de respuestas reutilizables.
* **Extensión** — captura de ofertas desde el navegador y autofill de formularios.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    if not settings.anthropic_api_key:
        log.warning(
            "ANTHROPIC_API_KEY no configurada: el sistema arranca en modo degradado "
            "(parsing heurístico, sin tailoring, intel ni simulacros)."
        )
    yield


app = FastAPI(
    title="Career Copilot API",
    description=DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # La extensión de navegador manda un Origin tipo chrome-extension://<id>,
    # que no se puede listar de antemano.
    allow_origin_regex=r"chrome-extension://.*|moz-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LLMUnavailable)
async def llm_unavailable_handler(request: Request, exc: LLMUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc), "code": "llm_unavailable"})


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    log.error("Fallo del LLM en %s: %s", request.url.path, exc)
    return JSONResponse(status_code=502, content={"detail": str(exc), "code": "llm_error"})


app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root():
    return {"name": "Career Copilot API", "docs": "/docs", "health": "/api/v1/health"}
