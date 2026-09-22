"""Simulador de entrevistas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class InterviewStartRequest(BaseModel):
    job_id: int | None = None
    resume_id: int | None = None
    mode: str = Field(default="mixed", description="technical | behavioral | system_design | mixed")
    difficulty: str = Field(default="medium", description="easy | medium | hard")
    language: str = Field(default="es", description="Idioma de la entrevista: es | en")


class InterviewTurn(BaseModel):
    role: str  # interviewer | candidate
    content: str
    feedback: dict | None = None


class AnswerFeedback(BaseModel):
    """Evaluación inmediata de una respuesta."""

    score: float = Field(default=0.0, description="0-100")
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(
        default_factory=list, description="Lo que un buen candidato habría mencionado"
    )
    star_compliance: str = Field(
        default="", description="Solo para preguntas behavioral: qué falta del método STAR"
    )
    model_answer: str = Field(default="", description="Una respuesta de referencia, concisa")


class InterviewReply(BaseModel):
    """Turno del entrevistador: feedback de lo anterior + siguiente pregunta."""

    feedback: AnswerFeedback = Field(default_factory=AnswerFeedback)
    next_question: str = Field(default="", description="Vacío si la entrevista terminó")
    question_type: str = ""
    is_final: bool = False


class InterviewSummary(BaseModel):
    overall_score: float = 0.0
    technical_score: float = 0.0
    communication_score: float = 0.0
    verdict: str = ""
    top_strengths: list[str] = Field(default_factory=list)
    priority_improvements: list[str] = Field(default_factory=list)
    study_plan: list[str] = Field(default_factory=list)


class InterviewSessionRead(BaseModel):
    id: int
    job_id: int | None = None
    resume_id: int | None = None
    mode: str
    transcript: list = Field(default_factory=list)
    summary: dict | None = None
    finished: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class AnswerRequest(BaseModel):
    answer: str


class QAEntryRead(BaseModel):
    id: int
    question: str
    answer: str
    tags: list = Field(default_factory=list)
    times_used: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class QAEntryWrite(BaseModel):
    question: str
    answer: str = ""
    tags: list[str] = Field(default_factory=list)
