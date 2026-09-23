"""Gestión de perfiles.

Un perfil es una fila de `users`: ya era la raíz de la que cuelgan CV,
postulaciones, simulacros, banco de respuestas y preferencias, así que convertir
la app en multiperfil no exige tocar el esquema. Ver ADR 0008.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Application, InterviewSession, Resume, User
from app.schemas.profile import ProfileRead
from app.schemas.resume import ResumeData


def is_default(user: User) -> bool:
    return user.email == settings.default_user_email


def summarize(db: Session, user: User) -> ProfileRead:
    resumes = db.scalar(select(func.count(Resume.id)).where(Resume.user_id == user.id)) or 0
    applications = (
        db.scalar(select(func.count(Application.id)).where(Application.user_id == user.id)) or 0
    )
    best = db.scalar(select(func.max(Resume.ats_score)).where(Resume.user_id == user.id))
    primary = db.scalar(
        select(Resume)
        .where(Resume.user_id == user.id)
        .order_by(Resume.is_primary.desc(), Resume.created_at.desc())
    )
    headline = ""
    if primary is not None:
        contact = (primary.parsed or {}).get("contact", {})
        headline = contact.get("headline") or primary.target_role or ""
    return ProfileRead(
        id=user.id,
        full_name=user.full_name or user.email,
        is_default=is_default(user),
        headline=headline,
        resumes=resumes,
        applications=applications,
        best_score=best,
        created_at=user.created_at,
    )


def list_profiles(db: Session) -> list[ProfileRead]:
    users = db.scalars(select(User).order_by(User.created_at)).all()
    return [summarize(db, u) for u in users]


def create_profile(db: Session, full_name: str) -> User:
    # El email es único en la tabla pero aquí no identifica a nadie: la app no
    # tiene login. Se genera uno sintético para no chocar entre perfiles.
    user = User(
        email=f"perfil-{uuid.uuid4().hex[:10]}@localhost",
        full_name=full_name.strip(),
        preferences={},
    )
    db.add(user)
    db.flush()
    return user


def _descendant_ids(db: Session, root_id: int) -> list[int]:
    """El CV y todas las variantes generadas a partir de él (tailoring)."""
    ids = [root_id]
    frontier = [root_id]
    while frontier:
        children = db.scalars(select(Resume.id).where(Resume.parent_id.in_(frontier))).all()
        frontier = [c for c in children if c not in ids]
        ids.extend(frontier)
    return ids


def move_resume_to_new_profile(db: Session, resume: Resume) -> User:
    """Crea un perfil con el nombre del CV y se lleva el CV, sus variantes y lo que cuelga de ellos.

    Sirve para separar CVs de personas distintas que se subieron al mismo perfil.
    """
    data = ResumeData.model_validate(resume.parsed or {})
    name = data.contact.full_name or resume.label or "Nuevo perfil"
    old_user_id = resume.user_id
    profile = create_profile(db, name)

    ids = _descendant_ids(db, resume.id)
    for row in db.scalars(select(Resume).where(Resume.id.in_(ids))):
        row.user_id = profile.id
        row.is_primary = row.id == resume.id

    # Las postulaciones hechas con esos CV se van con ellos, salvo que el perfil
    # destino ya tenga una para la misma vacante (restricción user+job).
    taken: set[int] = set()
    for app_row in db.scalars(
        select(Application).where(
            Application.user_id == old_user_id, Application.resume_id.in_(ids)
        )
    ):
        if app_row.job_id in taken:
            continue
        app_row.user_id = profile.id
        taken.add(app_row.job_id)

    for session in db.scalars(
        select(InterviewSession).where(
            InterviewSession.user_id == old_user_id, InterviewSession.resume_id.in_(ids)
        )
    ):
        session.user_id = profile.id

    db.flush()
    return profile
