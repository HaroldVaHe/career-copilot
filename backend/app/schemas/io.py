"""Modelos de request/response de la API para CV, tailoring y diffs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.ats import AtsReport
from app.schemas.resume import ResumeData


class ResumeSummary(BaseModel):
    id: int
    label: str
    target_role: str | None = None
    source_filename: str | None = None
    ats_score: float | None = None
    is_primary: bool = False
    parent_id: int | None = None
    tailored_for_job_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeRead(ResumeSummary):
    parsed: ResumeData = Field(default_factory=ResumeData)
    ats_report: AtsReport | None = None
    raw_text: str = ""


class ResumeUpdate(BaseModel):
    label: str | None = None
    target_role: str | None = None
    is_primary: bool | None = None
    parsed: ResumeData | None = None


class DiffLine(BaseModel):
    kind: Literal["equal", "insert", "delete"] = "equal"
    text: str = ""


class BulletDiff(BaseModel):
    """Diff estilo Git de un bullet: original vs. propuesta."""

    experience_index: int = 0
    bullet_index: int = 0
    company: str = ""
    role: str = ""
    original: str = ""
    suggestion: str = ""
    rationale: str = ""
    invented_facts: bool = False
    words: list[DiffLine] = Field(default_factory=list)


class TailorRequest(BaseModel):
    resume_id: int
    job_id: int | None = None
    job_description: str | None = Field(
        default=None, description="Alternativa a job_id: pegar la descripción directamente"
    )
    inject_gaps: bool = Field(
        default=False,
        description="Reescribir integrando las tecnologías que faltan. Solo se permiten si el "
        "usuario realmente las tiene: el modelo marca cualquier invención con invented_facts.",
    )
    tone: str = Field(default="professional", description="professional | direct | warm")


class TailorResponse(BaseModel):
    resume_id: int
    job_id: int | None = None
    summary_before: str = ""
    summary_after: str = ""
    summary_diff: list[DiffLine] = Field(default_factory=list)
    bullet_diffs: list[BulletDiff] = Field(default_factory=list)
    added_keywords: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SaveVariantRequest(BaseModel):
    """Guarda una versión adaptada tras revisar el diff."""

    resume_id: int
    job_id: int | None = None
    label: str = "Variante adaptada"
    target_role: str | None = None
    accepted_summary: str | None = None
    accepted_bullets: list[BulletDiff] = Field(
        default_factory=list, description="Solo los bullets que el usuario aceptó"
    )


class TailoredBullet(BaseModel):
    experience_index: int = Field(default=0, description="Índice del trabajo en `experience`")
    bullet_index: int = Field(default=0, description="Índice del bullet dentro de ese trabajo")
    suggestion: str = Field(default="", description="Bullet reescrito, listo para pegar")
    rationale: str = Field(default="", description="Por qué esta versión encaja mejor con la oferta")
    invented_facts: bool = Field(
        default=False, description="true si la sugerencia contiene datos ausentes del CV original"
    )


class TailoredResumeDraft(BaseModel):
    """Lo que devuelve Claude al adaptar el CV."""

    summary: str = Field(default="", description="Resumen profesional reescrito para esta vacante")
    bullets: list[TailoredBullet] = Field(default_factory=list)
    added_keywords: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(
        default_factory=list,
        description="Avisos al usuario: afirmaciones que debe verificar antes de usar",
    )
