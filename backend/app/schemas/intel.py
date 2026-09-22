"""Inteligencia de empresa, proceso de entrevista y negociación salarial."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    title: str = ""
    summary: str = ""
    url: str = ""
    date: str = ""


class CompanyIntelData(BaseModel):
    company_name: str = ""
    summary: str = Field(default="", description="Qué hace la empresa, en 3-4 frases")
    industry: str = ""
    size: str = Field(default="", description="Ej. '50-200 empleados' o 'no determinado'")
    headquarters: str = ""
    founded: str = ""
    funding_stage: str = ""
    culture_notes: list[str] = Field(
        default_factory=list, description="Cómo es trabajar ahí, según fuentes públicas"
    )
    tech_stack: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    recent_news: list[NewsItem] = Field(default_factory=list)
    talking_points: list[str] = Field(
        default_factory=list,
        description="Cosas concretas que mencionar en la entrevista para demostrar investigación",
    )
    questions_to_ask: list[str] = Field(
        default_factory=list, description="Preguntas inteligentes para hacerle al entrevistador"
    )
    sources: list[str] = Field(default_factory=list, description="URLs consultadas")
    confidence: str = Field(
        default="low", description="high | medium | low — qué tan sólida es esta información"
    )


class InterviewStage(BaseModel):
    order: int = 0
    name: str = Field(default="", description="Ej. 'Screening con RRHH', 'Live coding'")
    format: str = Field(default="", description="llamada, take-home, panel, live coding...")
    duration: str = ""
    focus: str = Field(default="", description="Qué evalúan en esta etapa")
    how_to_prepare: list[str] = Field(default_factory=list)


class CommonQuestion(BaseModel):
    question: str = ""
    type: str = Field(default="", description="technical | behavioral | system_design | culture")
    why_asked: str = ""


class InterviewIntelData(BaseModel):
    company_name: str = ""
    role: str = ""
    stages: list[InterviewStage] = Field(default_factory=list)
    assessment_types: list[str] = Field(
        default_factory=list,
        description="Ej. LeetCode medium, take-home de 4h, psicotécnico, STAR behavioral",
    )
    common_questions: list[CommonQuestion] = Field(default_factory=list)
    technical_topics: list[str] = Field(
        default_factory=list, description="Temas concretos a repasar para ESTA vacante"
    )
    difficulty: str = Field(default="", description="low | medium | high")
    typical_duration: str = Field(default="", description="Duración total del proceso")
    tips: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    confidence: str = "low"


class SalaryBenchmark(BaseModel):
    role: str = ""
    location: str = ""
    currency: str = ""
    period: str = "year"
    p25: float = 0.0
    p50: float = 0.0
    p75: float = 0.0
    reasoning: str = Field(default="", description="De dónde salen estas cifras")
    negotiation_script: list[str] = Field(
        default_factory=list, description="Frases concretas para la conversación de oferta"
    )
    leverage_points: list[str] = Field(
        default_factory=list, description="Qué del perfil justifica pedir el rango alto"
    )
    sources: list[str] = Field(default_factory=list)
    confidence: str = "low"


class CoverLetterDraft(BaseModel):
    subject: str = Field(default="", description="Asunto sugerido si se envía por email")
    body: str = Field(default="", description="Carta completa, lista para enviar")
    highlighted_projects: list[str] = Field(
        default_factory=list, description="Proyectos del CV que se usaron como argumento"
    )
    word_count: int = 0
