from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.session import engine


def database_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not database_available(),
    reason="Postgres no está arriba. Arráncalo con `docker compose up -d`.",
)


@pytest.fixture(scope="session")
def client():
    """TestClient con el esquema ya creado. Solo para los tests marcados `needs_db`."""
    from fastapi.testclient import TestClient

    from app.db.init_db import init_db
    from app.main import app

    init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_resume_text() -> str:
    return """Ana Vargas
Backend Engineer
ana.vargas@example.com | +34 600 123 456 | Madrid, España
linkedin.com/in/anavargas | github.com/anavargas

RESUMEN
Ingeniera backend con 5 años construyendo APIs en Python y Go.

EXPERIENCIA
Senior Backend Engineer - Fintech SA (2021-01 - present)
• Lideré la migración de un monolito Django a microservicios en Kubernetes,
  reduciendo el p99 de 800ms a 180ms
• Diseñé la capa de eventos con Kafka procesando 2M mensajes/día
• Responsable de las integraciones con PostgreSQL y Redis

EDUCACIÓN
Ingeniería Informática - Universidad Politécnica (2015 - 2019)

HABILIDADES
Python, Go, FastAPI, Django, PostgreSQL, Redis, Kafka, Docker, Kubernetes, AWS
"""


@pytest.fixture
def sample_job_text() -> str:
    return """Senior Backend Engineer (Remoto)

Requisitos imprescindibles:
- 5+ años de experiencia en Python
- Kubernetes y Docker
- PostgreSQL

Valorable:
- Go
- GraphQL

Ofrecemos 65000 - 85000 EUR anuales. 100% remoto.
"""
