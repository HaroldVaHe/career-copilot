"""Subrama de inteligencia por vacante: empresa, proceso y salario."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession, JobDep, resolve_resume
from app.schemas.intel import CompanyIntelData, InterviewIntelData, SalaryBenchmark
from app.schemas.job import MatchResult
from app.services import intel as intel_service
from app.services import matching
from app.services.llm import LLMError, LLMUnavailable

router = APIRouter(prefix="/intel", tags=["Inteligencia"])


class JobBrief(BaseModel):
    """Dossier completo de una vacante: todo lo que necesitas antes de postular."""

    job_id: int
    company: CompanyIntelData | None = None
    interview: InterviewIntelData | None = None
    salary: SalaryBenchmark | None = None
    match: MatchResult | None = None
    errors: list[str] = []


@router.get("/company", response_model=CompanyIntelData)
def company_intel(db: DbSession, name: str = Query(..., min_length=2), force: bool = False):
    """Investiga una empresa por nombre. Se cachea 14 días."""
    try:
        return intel_service.research_company(db, name, force=force)
    except LLMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


@router.get("/jobs/{job_id}/company", response_model=CompanyIntelData)
def company_intel_for_job(job: JobDep, db: DbSession, force: bool = False):
    if not job.company:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La vacante no tiene empresa asociada.")
    try:
        return intel_service.research_company(db, job.company, force=force)
    except LLMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/jobs/{job_id}/interview", response_model=InterviewIntelData)
def interview_intel_for_job(job: JobDep, db: DbSession, force: bool = False):
    """Qué tipo de pruebas usa esta empresa y qué preguntas reporta la gente."""
    try:
        return intel_service.research_interview_process(
            db, job.company, job.title, job=job, force=force
        )
    except LLMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/jobs/{job_id}/salary", response_model=SalaryBenchmark)
def salary_for_job(job: JobDep, db: DbSession, user: CurrentUser, resume_id: int | None = None):
    """Rango real de mercado y guion de negociación."""
    resume = None
    try:
        resume = resolve_resume(db, user, resume_id)
    except HTTPException:
        pass
    try:
        return intel_service.salary_benchmark(
            job.title, job.location or "remoto internacional", job.seniority or "", resume
        )
    except LLMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/jobs/{job_id}/brief", response_model=JobBrief)
def job_brief(
    job: JobDep,
    db: DbSession,
    user: CurrentUser,
    resume_id: int | None = None,
    include_salary: bool = True,
):
    """Dossier completo. Cada bloque falla de forma aislada: si la investigación
    de una parte no sale, el resto se devuelve igual."""
    brief = JobBrief(job_id=job.id, errors=[])

    try:
        resume = resolve_resume(db, user, resume_id)
        brief.match = matching.upsert(db, resume, job, with_analysis=True)
    except HTTPException as exc:
        brief.errors.append(f"match: {exc.detail}")
    except LLMError as exc:
        brief.errors.append(f"match: {exc}")

    for label, fn in (
        ("empresa", lambda: intel_service.research_company(db, job.company)),
        (
            "entrevista",
            lambda: intel_service.research_interview_process(db, job.company, job.title, job=job),
        ),
    ):
        try:
            value = fn()
            setattr(brief, "company" if label == "empresa" else "interview", value)
        except LLMError as exc:
            brief.errors.append(f"{label}: {exc}")

    if include_salary:
        try:
            brief.salary = intel_service.salary_benchmark(
                job.title, job.location or "remoto internacional", job.seniority or ""
            )
        except LLMError as exc:
            brief.errors.append(f"salario: {exc}")

    return brief
