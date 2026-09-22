"""Módulo 3 — Puente con la extensión de navegador: captura y autofill.

Esta es la vía soportada para LinkedIn, Indeed, Glassdoor, Workday, Greenhouse,
Lever y Taleo. En lugar de scrapear sus servidores (algo que sus términos de uso
prohíben y que te puede costar la cuenta), la extensión lee la página que TÚ ya
tienes abierta, en TU sesión, y la manda aquí.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, resolve_resume
from app.models import Application, QAEntry
from app.schemas.job import JobRead, MatchResult
from app.schemas.resume import ResumeData
from app.services import jobs as job_service
from app.services import matching
from app.services.documents import html_to_text
from app.services.embeddings import cosine, embed
from app.services.llm import LLMError, as_prompt_json, llm
from app.services.sources import RawJob

router = APIRouter(prefix="/capture", tags=["Extensión"])


class CapturePayload(BaseModel):
    url: str
    title: str = ""
    company: str = ""
    location: str = ""
    description_html: str = ""
    description_text: str = ""
    source: str = Field(default="extension", description="linkedin, indeed, workday...")
    analyze: bool = Field(default=True, description="Extraer requisitos con Claude")


class CaptureResponse(BaseModel):
    job: JobRead
    match: MatchResult | None = None
    application_id: int | None = None
    created: bool


@router.get("/ping")
def ping(user: CurrentUser):
    """La extensión llama aquí al cargar para confirmar que la API responde."""
    return {"ok": True, "user": user.email, "llm": llm.available}


@router.post("", response_model=CaptureResponse, status_code=status.HTTP_201_CREATED)
def capture(payload: CapturePayload, db: DbSession, user: CurrentUser):
    """Guarda la vacante capturada y devuelve el match score al instante."""
    text = payload.description_text.strip() or html_to_text(payload.description_html)
    if not text:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "La captura no trae descripción. Abre la oferta completa antes de capturar.",
        )

    raw = RawJob(
        source=payload.source or "extension",
        external_id=payload.url,
        title=payload.title,
        company=payload.company,
        url=payload.url,
        location=payload.location,
        description_raw=text,
    )
    job, created = job_service.upsert_job(db, raw, analyze=payload.analyze)
    db.flush()

    match = None
    try:
        resume = resolve_resume(db, user, None)
        match = matching.upsert(db, resume, job)
    except HTTPException:
        pass

    existing = db.scalar(
        select(Application).where(Application.user_id == user.id, Application.job_id == job.id)
    )
    return CaptureResponse(
        job=JobRead.model_validate(job),
        match=match,
        application_id=existing.id if existing else None,
        created=created,
    )


class AutofillProfile(BaseModel):
    """Valores con los que la extensión rellena los formularios."""

    full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    years_experience: float = 0.0
    current_role: str = ""
    current_company: str = ""
    highest_degree: str = ""
    salary_expectation: str = ""
    work_authorization: str = ""
    requires_sponsorship: str = ""
    notice_period: str = ""
    preferred_pronouns: str = ""


@router.get("/autofill", response_model=AutofillProfile)
def autofill_profile(db: DbSession, user: CurrentUser, resume_id: int | None = None):
    """Perfil normalizado para el autofill de Workday, Greenhouse, Lever y compañía.

    Los campos que no salen del CV (autorización de trabajo, salario pretendido,
    preaviso) viven en `user.preferences`; edítalos en Ajustes.
    """
    resume = resolve_resume(db, user, resume_id)
    data = ResumeData.model_validate(resume.parsed or {})
    prefs = user.preferences or {}

    name_parts = data.contact.full_name.split()
    current = next((e for e in data.experience if e.is_current), None) or (
        data.experience[0] if data.experience else None
    )

    return AutofillProfile(
        full_name=data.contact.full_name,
        first_name=name_parts[0] if name_parts else "",
        last_name=" ".join(name_parts[1:]) if len(name_parts) > 1 else "",
        email=data.contact.email,
        phone=data.contact.phone,
        location=data.contact.location,
        linkedin=data.contact.linkedin,
        github=data.contact.github,
        portfolio=data.contact.portfolio,
        years_experience=data.total_years_experience,
        current_role=current.role if current else "",
        current_company=current.company if current else "",
        highest_degree=data.education[0].degree if data.education else "",
        salary_expectation=prefs.get("salary_expectation", ""),
        work_authorization=prefs.get("work_authorization", ""),
        requires_sponsorship=prefs.get("requires_sponsorship", ""),
        notice_period=prefs.get("notice_period", ""),
        preferred_pronouns=prefs.get("preferred_pronouns", ""),
    )


class FormQuestion(BaseModel):
    question: str
    job_id: int | None = None
    max_words: int = Field(default=120, ge=20, le=500)


class FormAnswer(BaseModel):
    answer: str
    source: str = Field(description="'knowledge_base' si se reutilizó una respuesta guardada")
    reused_entry_id: int | None = None
    confidence: str = "medium"


@router.post("/answer", response_model=FormAnswer)
def answer_form_question(payload: FormQuestion, db: DbSession, user: CurrentUser):
    """Responde una pregunta abierta de un formulario reutilizando tu banco de respuestas.

    Si ya escribiste algo muy parecido, se devuelve tal cual (no hay razón para
    pagar una llamada al modelo por la quincuagésima vez que te preguntan por qué
    quieres trabajar ahí). Si no, se redacta desde el CV y se guarda.
    """
    entries = db.scalars(select(QAEntry).where(QAEntry.user_id == user.id)).all()
    query_vec = embed(payload.question)

    best, best_score = None, 0.0
    for entry in entries:
        score = cosine(entry.embedding, query_vec)
        if score > best_score:
            best, best_score = entry, score

    if best is not None and best_score >= 0.85 and best.answer.strip():
        best.times_used += 1
        db.flush()
        return FormAnswer(
            answer=best.answer,
            source="knowledge_base",
            reused_entry_id=best.id,
            confidence="high",
        )

    if not llm.available:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No hay respuesta guardada parecida y falta ANTHROPIC_API_KEY para redactar una.",
        )

    resume = resolve_resume(db, user, None)
    data = ResumeData.model_validate(resume.parsed or {})

    from app.models import Job

    job = db.get(Job, payload.job_id) if payload.job_id else None
    job_block = (
        f"\n\nVacante:\n{job.title} en {job.company}\n{(job.description_raw or '')[:6000]}"
        if job
        else ""
    )
    similar = (
        f"\n\nRespuesta parecida que ya escribiste (adáptala, no la copies):\n"
        f"P: {best.question}\nR: {best.answer}"
        if best is not None and best_score >= 0.6
        else ""
    )

    try:
        answer_text = llm.complete(
            system=(
                "Respondes preguntas de formularios de postulación en primera persona, con la voz "
                "del candidato. Solo usas hechos de su CV — cero invenciones. Concreto y sin "
                "relleno corporativo. Devuelves únicamente el texto de la respuesta, sin preámbulo."
            ),
            user=(
                f"Pregunta del formulario: {payload.question}\n"
                f"Máximo {payload.max_words} palabras.\n\n"
                f"CV del candidato:\n{as_prompt_json(data)}{job_block}{similar}"
            ),
            effort="medium",
            max_tokens=2000,
        )
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    entry = QAEntry(
        user_id=user.id,
        question=payload.question,
        answer=answer_text,
        tags=["autogenerada"],
        times_used=1,
        embedding=query_vec,
    )
    db.add(entry)
    db.flush()

    return FormAnswer(answer=answer_text, source="generated", confidence="medium")
