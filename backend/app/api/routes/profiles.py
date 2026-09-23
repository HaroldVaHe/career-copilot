"""Perfiles: varias personas en la misma instalación, cada una con sus datos."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession, ResumeDep
from app.models import User
from app.schemas.profile import ProfileRead, ProfileWrite
from app.services import profiles as profile_service

router = APIRouter(prefix="/profiles", tags=["Perfiles"])


def _get_profile(db, profile_id: int) -> User:
    user = db.get(User, profile_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Perfil {profile_id} no encontrado")
    return user


@router.get("", response_model=list[ProfileRead])
def list_profiles(db: DbSession):
    return profile_service.list_profiles(db)


@router.get("/current", response_model=ProfileRead)
def current_profile(db: DbSession, user: CurrentUser):
    """El perfil que resuelve la cabecera `X-Profile-Id` (o el por defecto)."""
    return profile_service.summarize(db, user)


@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileWrite, db: DbSession):
    user = profile_service.create_profile(db, payload.full_name)
    return profile_service.summarize(db, user)


@router.patch("/{profile_id}", response_model=ProfileRead)
def rename_profile(profile_id: int, payload: ProfileWrite, db: DbSession):
    user = _get_profile(db, profile_id)
    user.full_name = payload.full_name.strip()
    db.flush()
    return profile_service.summarize(db, user)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: int, db: DbSession):
    """Borra el perfil y todo lo suyo: CV, postulaciones, simulacros y respuestas."""
    user = _get_profile(db, profile_id)
    if profile_service.is_default(user):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "El perfil por defecto no se puede borrar: es el que usan los clientes sin perfil.",
        )
    db.delete(user)


@router.post(
    "/from-resume/{resume_id}", response_model=ProfileRead, status_code=status.HTTP_201_CREATED
)
def split_resume(resume: ResumeDep, db: DbSession):
    """Mueve un CV del perfil activo a un perfil nuevo con el nombre de su titular.

    Se lleva también sus variantes adaptadas, las postulaciones y simulacros hechos con él.
    """
    user = profile_service.move_resume_to_new_profile(db, resume)
    return profile_service.summarize(db, user)
