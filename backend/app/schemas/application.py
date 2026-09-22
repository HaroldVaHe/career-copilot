"""CRM de postulaciones: Kanban, tareas y timeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models import ApplicationStatus, TaskCategory
from app.schemas.job import JobRead


class TaskRead(BaseModel):
    id: int
    title: str
    detail: str = ""
    category: str = TaskCategory.OTHER.value
    done: bool = False
    due_at: datetime | None = None
    order_index: int = 0

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str
    detail: str = ""
    category: str = TaskCategory.OTHER.value
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    detail: str | None = None
    category: str | None = None
    done: bool | None = None
    due_at: datetime | None = None
    order_index: int | None = None


class EventCreate(BaseModel):
    kind: str = "note"
    title: str = ""
    payload: dict = Field(default_factory=dict)


class EventRead(BaseModel):
    id: int
    kind: str
    title: str
    payload: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationCreate(BaseModel):
    job_id: int
    resume_id: int | None = None
    status: str = ApplicationStatus.SAVED.value
    notes: str = ""
    generate_tasks: bool = Field(
        default=True, description="Generar el checklist de preparación con Claude"
    )


class ApplicationUpdate(BaseModel):
    status: str | None = None
    resume_id: int | None = None
    notes: str | None = None
    cover_letter: str | None = None
    next_action_at: datetime | None = None
    salary_expectation: str | None = None
    contact_name: str | None = None
    contact_url: str | None = None
    board_order: int | None = None


class ApplicationRead(BaseModel):
    id: int
    job_id: int
    resume_id: int | None = None
    status: str
    board_order: int = 0
    notes: str = ""
    cover_letter: str | None = None
    applied_at: datetime | None = None
    next_action_at: datetime | None = None
    salary_expectation: str | None = None
    contact_name: str | None = None
    contact_url: str | None = None
    created_at: datetime
    updated_at: datetime
    job: JobRead | None = None
    tasks: list[TaskRead] = Field(default_factory=list)
    match_score: float | None = None

    model_config = {"from_attributes": True}


class BoardColumn(BaseModel):
    status: str
    label: str
    applications: list[ApplicationRead] = Field(default_factory=list)


class Board(BaseModel):
    columns: list[BoardColumn]
    stats: dict = Field(default_factory=dict)


class GeneratedTask(BaseModel):
    """Una tarea propuesta por el LLM."""

    title: str = ""
    detail: str = Field(default="", description="Cómo hacerla, en 1-2 frases concretas")
    category: str = Field(
        default="other", description="study | storytelling | networking | follow_up | logistics | other"
    )
    days_from_now: int = Field(default=0, description="Cuándo vence, en días desde hoy. 0 = sin fecha")


class TaskPlan(BaseModel):
    tasks: list[GeneratedTask] = Field(default_factory=list)
