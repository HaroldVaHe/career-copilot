from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models import Application, Job, Resume
from app.services.llm import llm
from app.services.sources import available_sources

router = APIRouter(tags=["Sistema"])


@router.get("/health")
def health(db: DbSession):
    """Estado del sistema y de sus dependencias."""
    try:
        db.execute(select(1))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "llm": {
            "configured": llm.available,
            "model": settings.llm_model,
            "effort": settings.llm_effort,
        },
        "embeddings": {
            "provider": settings.embedding_provider,
            "dim": settings.embedding_dim,
        },
        "job_sources": available_sources(),
    }


@router.get("/stats")
def stats(db: DbSession, user: CurrentUser):
    """Números del panel principal."""
    return {
        "resumes": db.scalar(select(func.count(Resume.id)).where(Resume.user_id == user.id)) or 0,
        "jobs_indexed": db.scalar(select(func.count(Job.id))) or 0,
        "applications": db.scalar(
            select(func.count(Application.id)).where(Application.user_id == user.id)
        )
        or 0,
        "best_resume_score": db.scalar(
            select(func.max(Resume.ats_score)).where(Resume.user_id == user.id)
        ),
    }


@router.get("/preferences")
def get_preferences(user: CurrentUser):
    """Datos que no salen del CV y que usa el autofill (salario, visado, preaviso)."""
    return user.preferences or {}


@router.put("/preferences")
def set_preferences(payload: dict, db: DbSession, user: CurrentUser):
    user.preferences = {**(user.preferences or {}), **payload}
    db.flush()
    return user.preferences
