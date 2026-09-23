"""Módulo 1 — Ingesta, auditoría y optimización de CV."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, ResumeDep
from app.models import Job, Resume
from app.schemas.ats import AtsReport
from app.schemas.io import (
    ResumeRead,
    ResumeSummary,
    ResumeUpdate,
    SaveVariantRequest,
    TailorRequest,
    TailorResponse,
)
from app.schemas.resume import ResumeData
from app.services import ats as ats_service
from app.services import report_pdf
from app.services import resume as resume_service
from app.services import tailoring
from app.services.documents import UnsupportedDocument, parse_document
from app.services.embeddings import embed
from app.services.llm import LLMUnavailable

router = APIRouter(prefix="/resumes", tags=["CV"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    db: DbSession,
    user: CurrentUser,
    file: UploadFile = File(..., description="PDF, DOCX, TXT o MD"),
    label: str = Form("CV principal"),
    target_role: str | None = Form(None),
    make_primary: bool = Form(True),
):
    """Sube un CV: lo parsea, lo estructura con Claude y lo audita contra ATS."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"El archivo pesa {len(data) / 1e6:.1f} MB; el máximo es 10 MB.",
        )
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo está vacío.")

    try:
        parsed = parse_document(data, file.filename or "cv.pdf")
    except UnsupportedDocument as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"No se pudo leer el documento: {exc}"
        ) from exc

    if not parsed.text.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No se extrajo texto del documento. Si es un PDF escaneado, expórtalo desde el "
            "editor original en vez de escanearlo.",
        )

    structured = resume_service.extract_resume(parsed.text)
    report = ats_service.analyze(structured, parsed.text, parsed.signals, target_role)

    if make_primary:
        for other in db.scalars(select(Resume).where(Resume.user_id == user.id, Resume.is_primary)):
            other.is_primary = False

    row = Resume(
        user_id=user.id,
        label=label,
        target_role=target_role,
        source_filename=file.filename,
        raw_text=parsed.text,
        parsed=structured.model_dump(),
        ats_report=report.model_dump(),
        ats_score=report.overall_score,
        is_primary=make_primary,
        embedding=embed(resume_service.embedding_text(structured, parsed.text)),
    )
    db.add(row)
    db.flush()
    return _to_read(row)


@router.get("", response_model=list[ResumeSummary])
def list_resumes(db: DbSession, user: CurrentUser):
    rows = db.scalars(
        select(Resume)
        .where(Resume.user_id == user.id)
        .order_by(Resume.is_primary.desc(), Resume.created_at.desc())
    ).all()
    return [ResumeSummary.model_validate(r) for r in rows]


@router.get("/{resume_id}", response_model=ResumeRead)
def get_resume_detail(resume: ResumeDep):
    return _to_read(resume)


@router.patch("/{resume_id}", response_model=ResumeRead)
def update_resume(resume: ResumeDep, payload: ResumeUpdate, db: DbSession, user: CurrentUser):
    """Edita metadatos o el CV estructurado. Si cambia el contenido, se re-audita."""
    if payload.label is not None:
        resume.label = payload.label
    if payload.target_role is not None:
        resume.target_role = payload.target_role
    if payload.is_primary:
        for other in db.scalars(
            select(Resume).where(Resume.user_id == user.id, Resume.is_primary, Resume.id != resume.id)
        ):
            other.is_primary = False
        resume.is_primary = True

    if payload.parsed is not None:
        resume.parsed = payload.parsed.model_dump()
        resume.raw_text = tailoring._render_text(payload.parsed)
        report = ats_service.analyze(payload.parsed, resume.raw_text, target_role=resume.target_role)
        resume.ats_report = report.model_dump()
        resume.ats_score = report.overall_score
        resume.embedding = embed(resume_service.embedding_text(payload.parsed, resume.raw_text))

    db.flush()
    return _to_read(resume)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume: ResumeDep, db: DbSession):
    db.delete(resume)


@router.get(
    "/{resume_id}/report.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def resume_report_pdf(resume: ResumeDep):
    """Informe PDF con puntuación, quick wins, hallazgos, reescrituras, keywords y perfil."""
    data = ResumeData.model_validate(resume.parsed or {})
    report = AtsReport.model_validate(resume.ats_report) if resume.ats_report else None
    pdf = report_pdf.build_report_pdf(data, report, resume.target_role, resume.label)
    filename = report_pdf.report_filename(data, resume.label)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{resume_id}/audit", response_model=AtsReport)
def reaudit(resume: ResumeDep, db: DbSession, use_llm: bool = True):
    """Vuelve a auditar el CV. Útil tras editarlo o al cambiar el rol objetivo."""
    data = ResumeData.model_validate(resume.parsed or {})
    report = ats_service.analyze(
        data, resume.raw_text, target_role=resume.target_role, use_llm=use_llm
    )
    resume.ats_report = report.model_dump()
    resume.ats_score = report.overall_score
    db.flush()
    return report


@router.post("/tailor", response_model=TailorResponse)
def tailor_resume(payload: TailorRequest, db: DbSession, user: CurrentUser):
    """Genera la versión adaptada del CV y devuelve el diff para que la revises.

    No guarda nada: el usuario acepta cambio por cambio en `/variants`.
    """
    resume = db.get(Resume, payload.resume_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CV no encontrado")
    if not payload.job_id and not payload.job_description:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Indica `job_id` o pega la descripción en `job_description`."
        )

    job = db.get(Job, payload.job_id) if payload.job_id else None
    if payload.job_id and job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vacante no encontrada")

    try:
        return tailoring.tailor(
            resume, job, payload.job_description, payload.inject_gaps, payload.tone
        )
    except LLMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.post("/variants", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def save_variant(payload: SaveVariantRequest, db: DbSession, user: CurrentUser):
    """Guarda una variante del CV con los cambios aceptados."""
    resume = db.get(Resume, payload.resume_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CV no encontrado")

    variant = tailoring.save_variant(db, resume, payload)
    data = ResumeData.model_validate(variant.parsed or {})
    report = ats_service.analyze(data, variant.raw_text, target_role=variant.target_role)
    variant.ats_report = report.model_dump()
    variant.ats_score = report.overall_score
    db.flush()
    return _to_read(variant)


def _to_read(row: Resume) -> ResumeRead:
    return ResumeRead(
        id=row.id,
        label=row.label,
        target_role=row.target_role,
        source_filename=row.source_filename,
        ats_score=row.ats_score,
        is_primary=row.is_primary,
        parent_id=row.parent_id,
        tailored_for_job_id=row.tailored_for_job_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        parsed=ResumeData.model_validate(row.parsed or {}),
        ats_report=AtsReport.model_validate(row.ats_report) if row.ats_report else None,
        raw_text=row.raw_text or "",
    )
