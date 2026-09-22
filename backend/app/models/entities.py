"""Modelo de datos completo del Career Copilot.

Se guarda todo en Postgres. Los campos `JSONB` almacenan las estructuras que
produce el LLM (CV parseado, requisitos de vacante, intel de empresa...), y los
campos `Vector` alimentan la búsqueda semántica vía pgvector.
"""

from __future__ import annotations

import enum
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base, TimestampMixin

EMB_DIM = settings.embedding_dim


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------
class ApplicationStatus(str, enum.Enum):
    """Columnas del Kanban. El orden aquí es el orden del tablero."""

    SAVED = "saved"
    APPLIED = "applied"
    RECRUITER_CONTACT = "recruiter_contact"
    TECHNICAL_TEST = "technical_test"
    FINAL_INTERVIEW = "final_interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


ACTIVE_STATUSES = [
    ApplicationStatus.SAVED,
    ApplicationStatus.APPLIED,
    ApplicationStatus.RECRUITER_CONTACT,
    ApplicationStatus.TECHNICAL_TEST,
    ApplicationStatus.FINAL_INTERVIEW,
    ApplicationStatus.OFFER,
]


class RemoteType(str, enum.Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class TaskCategory(str, enum.Enum):
    STUDY = "study"
    STORYTELLING = "storytelling"
    NETWORKING = "networking"
    FOLLOW_UP = "follow_up"
    LOGISTICS = "logistics"
    OTHER = "other"


# --------------------------------------------------------------------------
# Usuario
# --------------------------------------------------------------------------
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    # Preferencias de búsqueda: roles objetivo, salario mínimo, países, etc.
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)

    resumes: Mapped[list["Resume"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    applications: Mapped[list["Application"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# --------------------------------------------------------------------------
# CV
# --------------------------------------------------------------------------
class Resume(Base, TimestampMixin):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    label: Mapped[str] = mapped_column(String(160), default="CV principal")
    target_role: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    raw_text: Mapped[str] = mapped_column(Text, default="")
    # ResumeData serializado (ver app/schemas/resume.py)
    parsed: Mapped[dict] = mapped_column(JSONB, default=dict)
    # AtsReport serializado
    ats_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ats_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMB_DIM), nullable=True)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    # Variante generada a partir de otro CV (tailoring para una vacante)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )
    tailored_for_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="resumes")

    __table_args__ = (Index("ix_resumes_user_primary", "user_id", "is_primary"),)


# --------------------------------------------------------------------------
# Vacantes
# --------------------------------------------------------------------------
class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source: Mapped[str] = mapped_column(String(64), default="manual", index=True)
    external_id: Mapped[str | None] = mapped_column(String(190), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    title: Mapped[str] = mapped_column(String(320), default="")
    company: Mapped[str] = mapped_column(String(320), default="", index=True)
    location: Mapped[str | None] = mapped_column(String(320), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    remote_type: Mapped[str] = mapped_column(String(16), default=RemoteType.UNKNOWN.value)
    seniority: Mapped[str | None] = mapped_column(String(48), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(48), nullable=True)

    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    salary_period: Mapped[str | None] = mapped_column(String(16), nullable=True)  # year | month | hour

    description_raw: Mapped[str] = mapped_column(Text, default="")
    # JobRequirements serializado: hard_skills, nice_to_have, responsabilidades...
    requirements: Mapped[dict] = mapped_column(JSONB, default=dict)
    tags: Mapped[list] = mapped_column(JSONB, default=list)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMB_DIM), nullable=True)

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_jobs_source_external"),
        Index("ix_jobs_company_title", "company", "title"),
    )


class JobMatch(Base, TimestampMixin):
    """Resultado cacheado de comparar un CV contra una vacante."""

    __tablename__ = "job_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)

    score: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_score: Mapped[float] = mapped_column(Float, default=0.0)
    skill_score: Mapped[float] = mapped_column(Float, default=0.0)
    seniority_score: Mapped[float] = mapped_column(Float, default=0.0)

    matched_skills: Mapped[list] = mapped_column(JSONB, default=list)
    missing_skills: Mapped[list] = mapped_column(JSONB, default=list)
    # Análisis cualitativo del LLM (opcional, se calcula bajo demanda)
    analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (UniqueConstraint("resume_id", "job_id", name="uq_match_resume_job"),)


# --------------------------------------------------------------------------
# CRM de postulaciones
# --------------------------------------------------------------------------
class Application(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(32), default=ApplicationStatus.SAVED.value, index=True
    )
    board_order: Mapped[int] = mapped_column(Integer, default=0)

    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    salary_expectation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped[User] = relationship(back_populates="applications")
    job: Mapped[Job] = relationship(lazy="joined")
    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="ApplicationEvent.id"
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="Task.order_index"
    )

    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_application_user_job"),)


class ApplicationEvent(Base, TimestampMixin):
    """Timeline: cambios de estado, emails, entrevistas, notas."""

    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(48), default="note")
    title: Mapped[str] = mapped_column(String(320), default="")
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)

    application: Mapped[Application] = relationship(back_populates="events")


class Task(Base, TimestampMixin):
    """Checklist accionable por postulación."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(400))
    detail: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default=TaskCategory.OTHER.value)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    application: Mapped[Application] = relationship(back_populates="tasks")


# --------------------------------------------------------------------------
# Inteligencia
# --------------------------------------------------------------------------
class CompanyIntel(Base, TimestampMixin):
    """Investigación de empresa cacheada (se refresca bajo demanda)."""

    __tablename__ = "company_intel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_key: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(320))
    # CompanyIntelData: summary, industry, size, culture, tech_stack, news, sources
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewInsight(Base, TimestampMixin):
    """Qué tipo de pruebas y preguntas usa una empresa/rol."""

    __tablename__ = "interview_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_key: Mapped[str] = mapped_column(String(320), index=True)
    role_key: Mapped[str] = mapped_column(String(320), default="")
    # stages, assessment_types, common_questions, difficulty, sources
    data: Mapped[dict] = mapped_column(JSONB, default=dict)

    __table_args__ = (UniqueConstraint("company_key", "role_key", name="uq_insight_company_role"),)


class InterviewSession(Base, TimestampMixin):
    """Simulacro de entrevista con feedback."""

    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )
    mode: Mapped[str] = mapped_column(String(32), default="mixed")  # technical | behavioral | mixed
    # [{role, content, feedback?}]
    transcript: Mapped[list] = mapped_column(JSONB, default=list)
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    finished: Mapped[bool] = mapped_column(Boolean, default=False)


class QAEntry(Base, TimestampMixin):
    """Banco personal de respuestas reutilizables (STAR, motivaciones, etc.)."""

    __tablename__ = "qa_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMB_DIM), nullable=True)
