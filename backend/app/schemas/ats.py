"""Auditoría ATS: puntuación, hallazgos y propuestas de reescritura."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "warning", "info"]


class AtsFinding(BaseModel):
    severity: Severity = "info"
    area: str = Field(default="", description="Ej. formato, cuantificación, keywords, contacto")
    message: str = Field(default="", description="Qué está mal, en una frase")
    fix: str = Field(default="", description="Qué hacer exactamente para arreglarlo")


class BulletRewrite(BaseModel):
    """Propuesta de reescritura de un bullet bajo la fórmula X-Y-Z de Google."""

    experience_index: int = Field(
        default=0, description="Índice del trabajo en la lista `experience` (0-based)"
    )
    bullet_index: int = Field(default=0, description="Índice del bullet dentro de ese trabajo")
    original: str = ""
    suggestion: str = Field(
        default="",
        description="Reescritura: 'Logré [X] medido por [Y] haciendo [Z]'. Nunca inventes cifras "
        "que no estén en el CV; si falta la métrica, usa un placeholder entre corchetes.",
    )
    rationale: str = Field(default="", description="Por qué la versión nueva es mejor")
    invented_facts: bool = Field(
        default=False,
        description="true si la sugerencia contiene datos que NO estaban en el CV original",
    )


class AtsScoreBreakdown(BaseModel):
    """Cada eje va de 0 a 100."""

    technical_relevance: float = 0.0
    clarity_format: float = 0.0
    achievement_quantification: float = 0.0
    skill_coverage: float = 0.0
    ats_parseability: float = 0.0


class AtsReport(BaseModel):
    overall_score: float = Field(default=0.0, description="Puntuación global 0-100")
    breakdown: AtsScoreBreakdown = Field(default_factory=AtsScoreBreakdown)
    findings: list[AtsFinding] = Field(default_factory=list)
    rewrites: list[BulletRewrite] = Field(default_factory=list)
    keyword_density: dict[str, int] = Field(
        default_factory=dict, description="Skill -> nº de apariciones en el CV"
    )
    missing_sections: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    quick_wins: list[str] = Field(
        default_factory=list, description="3-5 acciones de máximo impacto y mínimo esfuerzo"
    )


class AtsLlmReview(BaseModel):
    """Lo que devuelve Claude. El score determinista se calcula aparte en Python."""

    technical_relevance: float = Field(default=0.0, description="0-100")
    clarity_format: float = Field(default=0.0, description="0-100")
    achievement_quantification: float = Field(default=0.0, description="0-100")
    findings: list[AtsFinding] = Field(default_factory=list)
    rewrites: list[BulletRewrite] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    quick_wins: list[str] = Field(default_factory=list)
