"""Módulo 2 — Motor de vacantes: agregación, filtros y matching semántico."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DbSession, JobDep, resolve_resume
from app.db.session import SessionLocal
from app.models import Job
from app.schemas.job import (
    JobCreate,
    JobRead,
    JobSearchQuery,
    MatchAnalysis,
    MatchResult,
    SearchPlan,
)
from app.services import geo, job_search, matching
from app.services import jobs as job_service
from app.services.embeddings import embed
from app.services.llm import LLMError, LLMUnavailable
from app.services.sources import REGISTRY, RawJob, available_sources, default_sources

router = APIRouter(prefix="/jobs", tags=["Vacantes"])


class JobWithMatch(BaseModel):
    job: JobRead
    match: MatchResult | None = None


class SearchResponse(BaseModel):
    total: int
    results: list[JobWithMatch]
    resume_id: int | None = None


class IngestRequest(BaseModel):
    sources: list[str] = Field(default_factory=default_sources)
    query: str = ""
    queries: list[str] = Field(
        default_factory=list, description="Varias consultas; se lanzan todas contra cada fuente"
    )
    country: str = Field(
        default="", description="País de residencia: descarta vacantes no elegibles desde ahí"
    )
    resume_id: int | None = Field(
        default=None,
        description="Si no hay `query` ni `queries`, se usa el plan de búsqueda de este CV",
    )
    remember: bool = Field(
        default=True, description="Guardar consultas y país como plan de ese CV para la próxima vez"
    )
    limit: int = Field(default=20, ge=1, le=100, description="Máximo por fuente y consulta")
    analyze: bool = Field(
        default=False,
        description="Normalizar cada vacante con Claude al importarla (más lento y con costo)",
    )


@router.get("/sources")
def list_sources():
    """Fuentes de agregación disponibles."""
    return {
        "sources": available_sources(),
        "details": [
            {
                "name": s.name,
                "label": s.label or s.name,
                "description": s.description,
                "default": s.default_enabled,
                "filters_country": s.filters_country,
            }
            for s in REGISTRY.values()
        ],
        "note": "LinkedIn, Indeed y Glassdoor prohíben el scraping en sus términos. "
        "Para esos portales usa la extensión de navegador: captura la oferta que ya "
        "estás viendo en tu propia sesión.",
    }


@router.get("/search-plan", response_model=SearchPlan)
def search_plan(
    db: DbSession,
    user: CurrentUser,
    resume_id: int | None = None,
    refresh: bool = Query(False, description="Descarta el plan guardado y lo recalcula"),
):
    """Qué buscar para un CV: títulos de puesto en inglés y país de residencia."""
    resume = resolve_resume(db, user, resume_id)
    if refresh:
        job_search.forget_plan(user, resume.id)
        db.flush()
    return job_search.build_plan(resume, user)


@router.post("/ingest")
def ingest(payload: IngestRequest, db: DbSession, user: CurrentUser):
    """Descarga vacantes de las fuentes públicas y las indexa.

    Sin consultas explícitas y con `resume_id`, busca según el CV (ver `/jobs/search-plan`).
    """
    unknown = [s for s in payload.sources if s not in REGISTRY]
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Fuente(s) desconocida(s): {unknown}. Disponibles: {available_sources()}",
        )

    queries = [q.strip() for q in [*payload.queries, payload.query] if q and q.strip()]
    country = geo.canonical(payload.country)
    resume = None
    if payload.resume_id is not None:
        resume = resolve_resume(db, user, payload.resume_id)
        if not queries:
            plan = job_search.build_plan(resume, user)
            queries, country = plan.queries, country or plan.country
        elif payload.remember:
            job_search.remember_plan(user, resume.id, queries, country)
            db.commit()

    results = job_service.ingest_many(
        db, payload.sources, queries, payload.limit, country, payload.analyze
    )
    return {"results": results, "queries": queries, "country": country}


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: DbSession):
    """Alta manual: pega la descripción de una vacante y se analiza con Claude."""
    if not payload.description_raw.strip() and not payload.url:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Pega la descripción de la oferta o indica una URL."
        )

    raw = RawJob(
        source=payload.source or "manual",
        external_id="",
        title=payload.title,
        company=payload.company,
        url=payload.url or "",
        location=payload.location or "",
        description_raw=payload.description_raw,
    )
    job, _ = job_service.upsert_job(db, raw, analyze=payload.analyze)
    db.flush()
    return JobRead.model_validate(job)


@router.post("/search", response_model=SearchResponse)
def search(payload: JobSearchQuery, db: DbSession, user: CurrentUser, resume_id: int | None = None):
    """Búsqueda con filtros avanzados y match score contra tu CV.

    `semantic` busca por significado (embeddings); `q` busca por texto literal.
    Se pueden combinar.
    """
    resume = None
    try:
        resume = resolve_resume(db, user, resume_id)
    except HTTPException:
        pass  # sin CV cargado se puede buscar igual, solo que sin score

    stmt = select(Job)

    if payload.q:
        needle = f"%{payload.q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Job.title).like(needle),
                func.lower(Job.company).like(needle),
                func.lower(Job.description_raw).like(needle),
            )
        )
    if payload.company:
        stmt = stmt.where(func.lower(Job.company).like(f"%{payload.company.lower()}%"))
    if payload.remote_type:
        stmt = stmt.where(Job.remote_type.in_(payload.remote_type))
    if payload.seniority:
        stmt = stmt.where(Job.seniority.in_(payload.seniority))
    if payload.source:
        stmt = stmt.where(Job.source.in_(payload.source))
    if payload.country and payload.country.strip():
        # Mismo criterio que al importar: el país, su región, "worldwide" o sin ubicación.
        patterns = geo.sql_patterns(payload.country)
        stmt = stmt.where(
            or_(
                Job.location.is_(None),
                func.trim(Job.location) == "",
                func.lower(func.trim(Job.location)).in_(["remote", "remoto"]),
                *[Job.location.ilike(p) for p in patterns],
                *[Job.country.ilike(p) for p in patterns],
            )
        )
    if payload.salary_min:
        stmt = stmt.where(Job.salary_max >= payload.salary_min)
    if payload.posted_within_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=payload.posted_within_days)
        stmt = stmt.where(or_(Job.posted_at >= cutoff, Job.created_at >= cutoff))
    if payload.required_skills:
        for skill in payload.required_skills:
            stmt = stmt.where(Job.description_raw.ilike(f"%{skill}%"))

    if payload.semantic:
        query_vec = embed(payload.semantic)
        stmt = stmt.order_by(Job.embedding.cosine_distance(query_vec))
    elif payload.sort == "date":
        stmt = stmt.order_by(func.coalesce(Job.posted_at, Job.created_at).desc())
    elif payload.sort == "salary":
        stmt = stmt.order_by(Job.salary_max.desc().nullslast())
    else:
        stmt = stmt.order_by(Job.created_at.desc())

    # Se traen más de los pedidos porque el filtro por score se aplica en Python
    # (el score depende del CV y no está en la base).
    fetch_limit = payload.limit * 4 if payload.min_score else payload.limit
    candidates = db.scalars(stmt.offset(payload.offset).limit(fetch_limit)).all()

    scores = matching.rank(db, resume, candidates) if resume else {}
    items = [
        JobWithMatch(job=JobRead.model_validate(job), match=scores.get(job.id))
        for job in candidates
    ]

    if payload.min_score is not None:
        items = [i for i in items if i.match and i.match.score >= payload.min_score]
    if resume and payload.sort == "score" and not payload.semantic:
        items.sort(key=lambda i: i.match.score if i.match else 0, reverse=True)

    return SearchResponse(
        total=len(items),
        results=items[: payload.limit],
        resume_id=resume.id if resume else None,
    )


@router.get("/{job_id}", response_model=JobRead)
def get_job_detail(job: JobDep):
    return JobRead.model_validate(job)


@router.post("/{job_id}/analyze", response_model=JobRead)
def analyze_job(job: JobDep, db: DbSession):
    """Fuerza la extracción de requisitos con Claude (las importadas usan heurística)."""
    try:
        job_service.reanalyze(db, job)
    except LLMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return JobRead.model_validate(job)


@router.get("/{job_id}/match", response_model=MatchResult)
def get_match(
    job: JobDep,
    db: DbSession,
    user: CurrentUser,
    resume_id: int | None = None,
    deep: bool = Query(False, description="Añade el análisis cualitativo de Claude"),
):
    """Match score CV <-> vacante, con skills coincidentes y faltantes."""
    resume = resolve_resume(db, user, resume_id)
    try:
        return matching.upsert(db, resume, job, with_analysis=deep)
    except LLMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.post("/{job_id}/analysis", response_model=MatchAnalysis)
def deep_analysis(job: JobDep, db: DbSession, user: CurrentUser, resume_id: int | None = None):
    """Análisis cualitativo: argumentos de venta, gaps y cómo compensarlos."""
    resume = resolve_resume(db, user, resume_id)
    try:
        result = matching.upsert(db, resume, job, with_analysis=True)
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if result.analysis is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El análisis requiere ANTHROPIC_API_KEY configurada.",
        )
    return result.analysis


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job: JobDep, db: DbSession):
    db.delete(job)


@router.post("/reindex")
def reindex(background: BackgroundTasks):
    """Recalcula los embeddings de todas las vacantes y CVs.

    Necesario tras cambiar EMBEDDING_PROVIDER o EMBEDDING_DIM.
    """
    background.add_task(_reindex_all)
    return {"status": "reindexando en segundo plano"}


def _reindex_all() -> None:
    from app.models import Resume
    from app.schemas.resume import ResumeData
    from app.services.resume import embedding_text

    with SessionLocal() as db:
        for job in db.scalars(select(Job)):
            job.embedding = embed(job_service.embedding_text(job))
        for resume in db.scalars(select(Resume)):
            data = ResumeData.model_validate(resume.parsed or {})
            resume.embedding = embed(embedding_text(data, resume.raw_text or ""))
        db.commit()
