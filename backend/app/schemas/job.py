"""Vacantes: normalización, requisitos extraídos y matching."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SkillRequirement(BaseModel):
    name: str = Field(default="", description="Nombre canónico de la tecnología o habilidad")
    required: bool = Field(default=True, description="true = imprescindible, false = deseable")
    years: float = Field(default=0.0, description="Años pedidos, 0 si no se especifica")


class JobRequirements(BaseModel):
    """Lo que Claude extrae de una descripción de vacante."""

    hard_skills: list[SkillRequirement] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(
        default_factory=list, description="Requisitos excluyentes tal cual los redacta la oferta"
    )
    nice_to_have: list[str] = Field(default_factory=list)
    education_required: str = ""
    years_experience: float = Field(default=0.0, description="Años mínimos pedidos, 0 si no dice")
    seniority: str = Field(
        default="", description="intern, junior, mid, senior, lead, principal, manager"
    )
    languages: list[str] = Field(default_factory=list, description="Idiomas exigidos")
    benefits: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(
        default_factory=list,
        description="Señales de alerta: sueldo ausente, stack irreal, 'trabajamos bajo presión'...",
    )


class JobNormalized(BaseModel):
    """Campos estructurados que Claude deduce del texto crudo de la oferta."""

    title: str = ""
    company: str = ""
    location: str = ""
    country: str = ""
    remote_type: str = Field(default="unknown", description="remote | hybrid | onsite | unknown")
    employment_type: str = Field(default="", description="full-time, contract, internship...")
    seniority: str = ""
    salary_min: float = 0.0
    salary_max: float = 0.0
    salary_currency: str = ""
    salary_period: str = Field(default="", description="year | month | hour")
    tags: list[str] = Field(default_factory=list)
    requirements: JobRequirements = Field(default_factory=JobRequirements)


class MatchAnalysis(BaseModel):
    """Análisis cualitativo del encaje CV <-> vacante."""

    verdict: str = Field(default="", description="2-3 frases: ¿vale la pena postular?")
    strongest_arguments: list[str] = Field(
        default_factory=list, description="Los 3 puntos del CV que más venden para ESTA vacante"
    )
    gaps: list[str] = Field(default_factory=list, description="Qué falta y cuánto pesa")
    gap_mitigation: list[str] = Field(
        default_factory=list, description="Cómo compensar cada gap en la carta o entrevista"
    )
    keywords_to_add: list[str] = Field(
        default_factory=list, description="Términos de la oferta que deberían aparecer en el CV"
    )
    estimated_fit: float = Field(default=0.0, description="0-100, juicio del modelo")


class MatchResult(BaseModel):
    job_id: int
    resume_id: int
    score: float
    semantic_score: float
    skill_score: float
    seniority_score: float
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    analysis: MatchAnalysis | None = None


class JobRead(BaseModel):
    id: int
    source: str
    external_id: str | None = None
    url: str | None = None
    title: str
    company: str
    location: str | None = None
    country: str | None = None
    remote_type: str
    seniority: str | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    description_raw: str = ""
    requirements: dict = Field(default_factory=dict)
    tags: list = Field(default_factory=list)
    posted_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobCreate(BaseModel):
    """Alta manual de vacante: pegar texto, o pasar una URL."""

    title: str = ""
    company: str = ""
    url: str | None = None
    location: str | None = None
    description_raw: str = Field(default="", description="Texto completo de la oferta")
    source: str = "manual"
    analyze: bool = Field(default=True, description="Extraer requisitos con Claude al guardar")


class JobSearchQuery(BaseModel):
    q: str | None = None
    min_score: float | None = Field(default=None, ge=0, le=100)
    remote_type: list[str] | None = None
    seniority: list[str] | None = None
    company: str | None = None
    salary_min: float | None = None
    required_skills: list[str] | None = Field(
        default=None, description="Solo vacantes que mencionen TODAS estas tecnologías"
    )
    posted_within_days: int | None = None
    source: list[str] | None = None
    semantic: str | None = Field(
        default=None, description="Búsqueda por significado, no por palabra exacta"
    )
    limit: int = 50
    offset: int = 0
    sort: str = Field(default="score", description="score | date | salary")
