"""Módulo 4 — CRM de postulaciones: Kanban, checklist y timeline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import ApplicationDep, CurrentUser, DbSession, resolve_resume
from app.models import ACTIVE_STATUSES, Application, ApplicationEvent, ApplicationStatus, Job, Task
from app.schemas.application import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationUpdate,
    Board,
    BoardColumn,
    EventCreate,
    EventRead,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)
from app.schemas.intel import CoverLetterDraft
from app.schemas.job import JobRead
from app.services import intel as intel_service
from app.services import matching
from app.services.llm import LLMError, llm

router = APIRouter(prefix="/applications", tags=["Postulaciones"])

COLUMN_LABELS = {
    ApplicationStatus.SAVED: "Guardada",
    ApplicationStatus.APPLIED: "Aplicada",
    ApplicationStatus.RECRUITER_CONTACT: "Contacto reclutador",
    ApplicationStatus.TECHNICAL_TEST: "Prueba técnica",
    ApplicationStatus.FINAL_INTERVIEW: "Entrevista final",
    ApplicationStatus.OFFER: "Oferta",
    ApplicationStatus.REJECTED: "Rechazo",
    ApplicationStatus.WITHDRAWN: "Retirada",
}


@router.get("/board", response_model=Board)
def get_board(db: DbSession, user: CurrentUser, include_closed: bool = True):
    """Tablero Kanban completo con estadísticas del pipeline."""
    rows = db.scalars(
        select(Application)
        .where(Application.user_id == user.id)
        .order_by(Application.board_order, Application.updated_at.desc())
    ).all()

    statuses = list(ApplicationStatus) if include_closed else ACTIVE_STATUSES
    columns = [
        BoardColumn(
            status=stat.value,
            label=COLUMN_LABELS[stat],
            applications=[_to_read(db, a) for a in rows if a.status == stat.value],
        )
        for stat in statuses
    ]

    applied = sum(1 for a in rows if a.status != ApplicationStatus.SAVED.value)
    interviews = sum(
        1
        for a in rows
        if a.status
        in (
            ApplicationStatus.TECHNICAL_TEST.value,
            ApplicationStatus.FINAL_INTERVIEW.value,
            ApplicationStatus.OFFER.value,
        )
    )
    offers = sum(1 for a in rows if a.status == ApplicationStatus.OFFER.value)
    rejected = sum(1 for a in rows if a.status == ApplicationStatus.REJECTED.value)

    overdue = db.scalar(
        select(func.count(Task.id))
        .join(Application, Task.application_id == Application.id)
        .where(
            Application.user_id == user.id,
            Task.done.is_(False),
            Task.due_at < datetime.now(timezone.utc),
        )
    )

    return Board(
        columns=columns,
        stats={
            "total": len(rows),
            "applied": applied,
            "interviews": interviews,
            "offers": offers,
            "rejected": rejected,
            # Tasa de respuesta: de lo que enviaste, cuánto avanzó de fase.
            "response_rate": round(interviews / applied * 100, 1) if applied else 0.0,
            "offer_rate": round(offers / applied * 100, 1) if applied else 0.0,
            "overdue_tasks": overdue or 0,
        },
    )


@router.get("", response_model=list[ApplicationRead])
def list_applications(db: DbSession, user: CurrentUser, status_filter: str | None = None):
    stmt = select(Application).where(Application.user_id == user.id)
    if status_filter:
        stmt = stmt.where(Application.status == status_filter)
    rows = db.scalars(stmt.order_by(Application.updated_at.desc())).all()
    return [_to_read(db, a) for a in rows]


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(payload: ApplicationCreate, db: DbSession, user: CurrentUser):
    """Guarda una vacante en el pipeline y genera su checklist de preparación."""
    job = db.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vacante no encontrada")

    existing = db.scalar(
        select(Application).where(Application.user_id == user.id, Application.job_id == job.id)
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Esta vacante ya está en tu pipeline (postulación {existing.id}).",
        )

    resume = None
    try:
        resume = resolve_resume(db, user, payload.resume_id)
    except HTTPException:
        pass

    row = Application(
        user_id=user.id,
        job_id=job.id,
        resume_id=resume.id if resume else None,
        status=payload.status,
        notes=payload.notes,
        applied_at=datetime.now(timezone.utc)
        if payload.status != ApplicationStatus.SAVED.value
        else None,
    )
    db.add(row)
    db.flush()

    db.add(
        ApplicationEvent(
            application_id=row.id,
            kind="created",
            title=f"Guardada en el pipeline como «{COLUMN_LABELS[ApplicationStatus(payload.status)]}»",
        )
    )

    if payload.generate_tasks:
        missing = []
        if resume is not None:
            missing = matching.compute(resume, job).missing_skills
        _create_tasks(db, row, job, resume, missing)

    db.flush()
    return _to_read(db, row)


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application_detail(application: ApplicationDep, db: DbSession):
    return _to_read(db, application)


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application(application: ApplicationDep, payload: ApplicationUpdate, db: DbSession):
    """Mueve la tarjeta de columna o actualiza sus datos."""
    if payload.status and payload.status != application.status:
        try:
            new_status = ApplicationStatus(payload.status)
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Estado inválido. Válidos: {[s.value for s in ApplicationStatus]}",
            ) from exc

        previous = application.status
        old_label = COLUMN_LABELS[ApplicationStatus(previous)]
        application.status = new_status.value
        if new_status != ApplicationStatus.SAVED and application.applied_at is None:
            application.applied_at = datetime.now(timezone.utc)

        db.add(
            ApplicationEvent(
                application_id=application.id,
                kind="status_change",
                title=f"{old_label} → {COLUMN_LABELS[new_status]}",
                payload={"from": previous, "to": new_status.value},
            )
        )
        _auto_followups(db, application, new_status)

    for field in (
        "resume_id", "notes", "cover_letter", "next_action_at",
        "salary_expectation", "contact_name", "contact_url", "board_order",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(application, field, value)

    db.flush()
    return _to_read(db, application)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application: ApplicationDep, db: DbSession):
    db.delete(application)


# --------------------------------------------------------------------------
# Tareas
# --------------------------------------------------------------------------
@router.post("/{application_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def add_task(application: ApplicationDep, payload: TaskCreate, db: DbSession):
    order = max((t.order_index for t in application.tasks), default=-1) + 1
    task = Task(
        title=payload.title,
        detail=payload.detail,
        category=payload.category,
        due_at=payload.due_at,
        order_index=order,
    )
    application.tasks.append(task)
    db.flush()
    return TaskRead.model_validate(task)


@router.post("/{application_id}/tasks/generate", response_model=list[TaskRead])
def generate_tasks(application: ApplicationDep, db: DbSession, user: CurrentUser, replace: bool = False):
    """Regenera el checklist con Claude, usando la intel del proceso si existe."""
    job = application.job
    if replace:
        for task in list(application.tasks):
            if not task.done:
                db.delete(task)
        db.flush()

    from app.models import Resume

    resume = db.get(Resume, application.resume_id) if application.resume_id else None
    missing = matching.compute(resume, job).missing_skills if resume else []

    created = _create_tasks(db, application, job, resume, missing)
    db.flush()
    return [TaskRead.model_validate(t) for t in created]


@router.patch("/tasks/{task_id}", response_model=TaskRead, tags=["Postulaciones"])
def update_task(task_id: int, payload: TaskUpdate, db: DbSession, user: CurrentUser):
    task = db.get(Task, task_id)
    if task is None or task.application.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarea no encontrada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.flush()
    return TaskRead.model_validate(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Postulaciones"])
def delete_task(task_id: int, db: DbSession, user: CurrentUser):
    task = db.get(Task, task_id)
    if task is None or task.application.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarea no encontrada")
    db.delete(task)


# --------------------------------------------------------------------------
# Timeline
# --------------------------------------------------------------------------
@router.get("/{application_id}/events", response_model=list[EventRead])
def list_events(application: ApplicationDep):
    return [EventRead.model_validate(e) for e in application.events]


@router.post("/{application_id}/events", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def add_event(application: ApplicationDep, payload: EventCreate, db: DbSession):
    event = ApplicationEvent(
        application_id=application.id, kind=payload.kind, title=payload.title, payload=payload.payload
    )
    db.add(event)
    db.flush()
    return EventRead.model_validate(event)


# --------------------------------------------------------------------------
# Carta de presentación
# --------------------------------------------------------------------------
@router.post("/{application_id}/cover-letter", response_model=CoverLetterDraft)
def generate_cover_letter(
    application: ApplicationDep,
    db: DbSession,
    user: CurrentUser,
    use_company_intel: bool = True,
    tone: str = "professional",
    save: bool = True,
):
    """Genera la carta personalizada para esta vacante."""
    from app.models import Resume

    resume = db.get(Resume, application.resume_id) if application.resume_id else None
    if resume is None:
        resume = resolve_resume(db, user, None)

    company_data = None
    if use_company_intel and llm.available:
        try:
            company_data = intel_service.research_company(db, application.job.company)
        except LLMError:
            company_data = None

    try:
        draft = intel_service.cover_letter(resume, application.job, company_data, tone)
    except LLMError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    if save:
        application.cover_letter = draft.body
        db.add(
            ApplicationEvent(
                application_id=application.id,
                kind="cover_letter",
                title="Carta de presentación generada",
                payload={"word_count": draft.word_count},
            )
        )
        db.flush()
    return draft


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _create_tasks(db, application: Application, job: Job, resume, missing: list[str]) -> list[Task]:
    """Genera el checklist con IA si hay API key; si no, usa la plantilla base."""
    generated = None
    if llm.available:
        try:
            generated = intel_service.generate_tasks(resume, job, missing)
        except LLMError:
            generated = None
    if not generated:
        generated = intel_service.fallback_tasks(job, missing)

    start = max((t.order_index for t in application.tasks), default=-1) + 1
    created = []
    for offset, item in enumerate(generated):
        # Se añade por la relación, no por la FK: si se asigna `application_id`
        # a pelo, la colección `application.tasks` ya cargada no se entera y la
        # respuesta sale sin tareas.
        task = Task(
            title=item.title,
            detail=item.detail,
            category=item.category,
            due_at=(
                datetime.now(timezone.utc) + timedelta(days=item.days_from_now)
                if item.days_from_now
                else None
            ),
            order_index=start + offset,
        )
        application.tasks.append(task)
        created.append(task)
    db.flush()
    return created


def _auto_followups(db, application: Application, new_status: ApplicationStatus) -> None:
    """Al pasar a 'Aplicada' se programan los follow-ups; es lo que más se olvida."""
    if new_status != ApplicationStatus.APPLIED:
        return
    existing = {t.title for t in application.tasks}
    now = datetime.now(timezone.utc)
    for days, label in ((7, "Follow-up a los 5 días hábiles"), (14, "Follow-up a los 10 días hábiles")):
        if label in existing:
            continue
        application.tasks.append(
            Task(
                title=label,
                detail="Correo breve reiterando interés, con un dato nuevo sobre tu perfil.",
                category="follow_up",
                due_at=now + timedelta(days=days),
                order_index=999,
            )
        )
    application.next_action_at = now + timedelta(days=7)


def _to_read(db, row: Application) -> ApplicationRead:
    from app.models import JobMatch

    score = db.scalar(
        select(JobMatch.score).where(
            JobMatch.job_id == row.job_id, JobMatch.resume_id == row.resume_id
        )
    )
    return ApplicationRead(
        id=row.id,
        job_id=row.job_id,
        resume_id=row.resume_id,
        status=row.status,
        board_order=row.board_order,
        notes=row.notes,
        cover_letter=row.cover_letter,
        applied_at=row.applied_at,
        next_action_at=row.next_action_at,
        salary_expectation=row.salary_expectation,
        contact_name=row.contact_name,
        contact_url=row.contact_url,
        created_at=row.created_at,
        updated_at=row.updated_at,
        job=JobRead.model_validate(row.job) if row.job else None,
        tasks=[TaskRead.model_validate(t) for t in row.tasks],
        match_score=score,
    )
