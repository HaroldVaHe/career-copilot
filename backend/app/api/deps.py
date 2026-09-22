"""Dependencias compartidas de FastAPI."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import Application, Job, Resume, User

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession) -> User:
    """App de un solo usuario: siempre el perfil local del .env.

    Si algún día se abre a varios usuarios, este es el único punto a cambiar
    (leer el token, resolver el usuario) — el resto de la API ya depende de aquí.
    """
    user = db.scalar(select(User).where(User.email == settings.default_user_email))
    if user is None:
        user = User(email=settings.default_user_email, full_name=settings.default_user_name)
        db.add(user)
        db.flush()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_resume(resume_id: Annotated[int, Path()], db: DbSession, user: CurrentUser) -> Resume:
    resume = db.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"CV {resume_id} no encontrado")
    return resume


def get_job(job_id: Annotated[int, Path()], db: DbSession) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Vacante {job_id} no encontrada")
    return job


def get_application(
    application_id: Annotated[int, Path()], db: DbSession, user: CurrentUser
) -> Application:
    app_row = db.get(Application, application_id)
    if app_row is None or app_row.user_id != user.id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Postulación {application_id} no encontrada"
        )
    return app_row


def primary_resume(db: Session, user: User) -> Resume | None:
    """El CV marcado como principal, o el más reciente."""
    return db.scalar(
        select(Resume)
        .where(Resume.user_id == user.id)
        .order_by(Resume.is_primary.desc(), Resume.created_at.desc())
    )


def resolve_resume(db: Session, user: User, resume_id: int | None) -> Resume:
    resume = db.get(Resume, resume_id) if resume_id else primary_resume(db, user)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No hay ningún CV cargado. Sube uno en /api/v1/resumes primero.",
        )
    return resume


ResumeDep = Annotated[Resume, Depends(get_resume)]
JobDep = Annotated[Job, Depends(get_job)]
ApplicationDep = Annotated[Application, Depends(get_application)]
