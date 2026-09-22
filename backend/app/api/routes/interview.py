"""Simulador de entrevistas y banco personal de respuestas."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, resolve_resume
from app.models import InterviewSession, Job, QAEntry
from app.schemas.interview import (
    AnswerRequest,
    InterviewReply,
    InterviewSessionRead,
    InterviewStartRequest,
    InterviewSummary,
    QAEntryRead,
    QAEntryWrite,
)
from app.services import intel as intel_service
from app.services import interview as interview_service
from app.services.embeddings import cosine, embed
from app.services.llm import LLMError, LLMUnavailable

router = APIRouter(prefix="/interview", tags=["Entrevistas"])


class StartResponse(BaseModel):
    session: InterviewSessionRead
    reply: InterviewReply


@router.post("/sessions", response_model=StartResponse, status_code=status.HTTP_201_CREATED)
def start_session(payload: InterviewStartRequest, db: DbSession, user: CurrentUser):
    """Arranca un simulacro contextualizado con la vacante y tu CV."""
    job = db.get(Job, payload.job_id) if payload.job_id else None
    if payload.job_id and job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vacante no encontrada")

    resume = None
    try:
        resume = resolve_resume(db, user, payload.resume_id)
    except HTTPException:
        pass

    # Si ya investigamos cómo entrevista la empresa, el simulacro imita ese proceso.
    interview_data = None
    if job is not None and job.company:
        try:
            interview_data = intel_service.research_interview_process(db, job.company, job.title, job)
        except LLMError:
            interview_data = None

    try:
        session, reply = interview_service.start(
            db,
            user_id=user.id,
            job=job,
            resume=resume,
            mode=payload.mode,
            difficulty=payload.difficulty,
            language=payload.language,
            interview_data=interview_data,
        )
    except LLMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return StartResponse(session=InterviewSessionRead.model_validate(session), reply=reply)


@router.get("/sessions", response_model=list[InterviewSessionRead])
def list_sessions(db: DbSession, user: CurrentUser):
    rows = db.scalars(
        select(InterviewSession)
        .where(InterviewSession.user_id == user.id)
        .order_by(InterviewSession.created_at.desc())
    ).all()
    return [InterviewSessionRead.model_validate(r) for r in rows]


@router.get("/sessions/{session_id}", response_model=InterviewSessionRead)
def get_session(session_id: int, db: DbSession, user: CurrentUser):
    return InterviewSessionRead.model_validate(_owned(db, user, session_id))


@router.post("/sessions/{session_id}/answer", response_model=InterviewReply)
def answer(session_id: int, payload: AnswerRequest, db: DbSession, user: CurrentUser):
    """Responde a la pregunta actual y recibe feedback inmediato + la siguiente."""
    session = _owned(db, user, session_id)
    if not payload.answer.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La respuesta está vacía.")
    try:
        return interview_service.answer(db, session, payload.answer)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


@router.post("/sessions/{session_id}/finish", response_model=InterviewSummary)
def finish(session_id: int, db: DbSession, user: CurrentUser):
    """Cierra la entrevista y devuelve la evaluación global con plan de estudio."""
    session = _owned(db, user, session_id)
    try:
        return interview_service.finish(db, session)
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, db: DbSession, user: CurrentUser):
    db.delete(_owned(db, user, session_id))


# --------------------------------------------------------------------------
# Banco de preguntas y respuestas reutilizables
# --------------------------------------------------------------------------
@router.get("/qa", response_model=list[QAEntryRead])
def list_qa(db: DbSession, user: CurrentUser, search: str | None = None, limit: int = 50):
    """Tu repositorio de respuestas. `search` busca por significado, no por literal."""
    rows = db.scalars(
        select(QAEntry).where(QAEntry.user_id == user.id).order_by(QAEntry.times_used.desc())
    ).all()

    if search:
        query_vec = embed(search)
        rows = sorted(rows, key=lambda r: cosine(r.embedding, query_vec), reverse=True)

    return [QAEntryRead.model_validate(r) for r in rows[:limit]]


@router.post("/qa", response_model=QAEntryRead, status_code=status.HTTP_201_CREATED)
def create_qa(payload: QAEntryWrite, db: DbSession, user: CurrentUser):
    row = QAEntry(
        user_id=user.id,
        question=payload.question,
        answer=payload.answer,
        tags=payload.tags,
        embedding=embed(f"{payload.question}\n{payload.answer}"),
    )
    db.add(row)
    db.flush()
    return QAEntryRead.model_validate(row)


@router.patch("/qa/{entry_id}", response_model=QAEntryRead)
def update_qa(entry_id: int, payload: QAEntryWrite, db: DbSession, user: CurrentUser):
    row = db.get(QAEntry, entry_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entrada no encontrada")
    row.question = payload.question
    row.answer = payload.answer
    row.tags = payload.tags
    row.embedding = embed(f"{payload.question}\n{payload.answer}")
    db.flush()
    return QAEntryRead.model_validate(row)


@router.delete("/qa/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_qa(entry_id: int, db: DbSession, user: CurrentUser):
    row = db.get(QAEntry, entry_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entrada no encontrada")
    db.delete(row)


def _owned(db, user, session_id: int) -> InterviewSession:
    session = db.get(InterviewSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sesión no encontrada")
    return session
