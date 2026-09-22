"""Matching CV <-> vacante: score híbrido y análisis cualitativo.

El score no es solo coseno de embeddings. Un reclutador filtra por skills duras
antes que por "parecido general", así que el peso mayor se lo lleva la cobertura
de requisitos, y la similitud semántica actúa como desempate para lo que la
taxonomía no captura (dominio, tipo de producto, forma de trabajar).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Job, JobMatch, Resume
from app.schemas.job import MatchAnalysis, MatchResult
from app.schemas.resume import ResumeData
from app.services.embeddings import cosine
from app.services.llm import LLMError, as_prompt_json, llm
from app.services.taxonomy import canonicalize, extract_skills, seniority_distance

WEIGHTS = {"skills": 0.50, "semantic": 0.35, "seniority": 0.15}

# Peso relativo de un requisito deseable frente a uno excluyente.
NICE_TO_HAVE_WEIGHT = 0.35

_ANALYSIS_SYSTEM = """Analizas el encaje entre un candidato y una vacante concreta, como lo haría
un reclutador técnico honesto — no un animador.

- `verdict`: 2-3 frases. Di claramente si vale la pena postular y por qué. Si el encaje es malo,
  dilo; perder el tiempo del candidato es peor que un no.
- `strongest_arguments`: los 3 hechos del CV que más pesan PARA ESTA vacante, citando el dato
  concreto (empresa, métrica, tecnología). Nada genérico.
- `gaps`: qué falta y cuánto pesa realmente. Distingue un requisito excluyente de un "plus".
- `gap_mitigation`: cómo compensar cada gap con algo que el candidato SÍ tiene. Nunca sugieras
  afirmar experiencia inexistente.
- `keywords_to_add`: términos literales de la oferta que deberían aparecer en el CV y no están,
  siempre que el candidato tenga base real para usarlos.
- `estimated_fit`: 0-100, tu juicio. Sé exigente: 80+ significa que pasarías el filtro sin dudas.

Responde en español."""


def _calibrate_semantic(raw_cosine: float) -> float:
    """Los embeddings locales son bolsa-de-palabras: dos documentos del mismo
    dominio rara vez pasan de 0.5 de coseno. Sin reescalar, el eje semántico
    aplastaría todos los scores contra el suelo."""
    if settings.embedding_provider == "local":
        return min(1.0, raw_cosine / 0.55)
    return raw_cosine


def skill_breakdown(resume_data: ResumeData, job: Job, job_text: str = "") -> tuple[float, list[str], list[str]]:
    """(cobertura 0-1, skills coincidentes, skills que faltan)."""
    have = {s.lower() for s in (canonicalize(x) for x in resume_data.skills.flat()) if s}
    # Las tecnologías nombradas dentro de la experiencia también cuentan.
    experience_text = " ".join(
        b for exp in resume_data.experience for b in [*exp.bullets, *exp.technologies]
    )
    have |= {s.lower() for s in extract_skills(experience_text)}

    requirements = (job.requirements or {}).get("hard_skills") or []
    if not requirements:
        # Vacante sin requisitos estructurados: caemos a lo que diga el texto.
        detected = extract_skills(job_text or job.description_raw or "")
        requirements = [{"name": name, "required": True} for name in list(detected)[:20]]

    matched: list[str] = []
    missing: list[str] = []
    total_weight = matched_weight = 0.0

    for req in requirements:
        name = canonicalize(str(req.get("name", "")))
        if not name:
            continue
        weight = 1.0 if req.get("required", True) else NICE_TO_HAVE_WEIGHT
        total_weight += weight
        if name.lower() in have:
            matched.append(name)
            matched_weight += weight
        else:
            missing.append(name)

    coverage = matched_weight / total_weight if total_weight else 0.0
    return coverage, matched, missing


def seniority_fit(resume_data: ResumeData, job: Job) -> float:
    """1.0 encaje exacto; penaliza más estar por debajo que por encima."""
    candidate = resume_data.detected_seniority or ""
    required = (job.seniority or "") or (job.requirements or {}).get("seniority", "")
    distance = seniority_distance(candidate, required)
    if distance < 0:
        return 0.6  # desconocido: ni premia ni castiga
    if distance == 0:
        return 1.0
    if distance == 1:
        return 0.75
    if distance == 2:
        return 0.45
    return 0.2


def compute(resume: Resume, job: Job) -> MatchResult:
    resume_data = ResumeData.model_validate(resume.parsed or {})

    coverage, matched, missing = skill_breakdown(resume_data, job)
    semantic = _calibrate_semantic(cosine(resume.embedding, job.embedding))
    seniority = seniority_fit(resume_data, job)

    score = (
        coverage * WEIGHTS["skills"]
        + semantic * WEIGHTS["semantic"]
        + seniority * WEIGHTS["seniority"]
    ) * 100

    return MatchResult(
        job_id=job.id,
        resume_id=resume.id,
        score=round(score, 1),
        semantic_score=round(semantic * 100, 1),
        skill_score=round(coverage * 100, 1),
        seniority_score=round(seniority * 100, 1),
        matched_skills=matched,
        missing_skills=missing,
    )


def analyze(resume: Resume, job: Job) -> MatchAnalysis:
    """Análisis cualitativo con Claude. Requiere API key."""
    resume_data = ResumeData.model_validate(resume.parsed or {})
    result = compute(resume, job)

    user = f"""VACANTE
Título: {job.title}
Empresa: {job.company}
Ubicación: {job.location or 'no indicada'} ({job.remote_type})
Seniority pedido: {job.seniority or 'no indicado'}

Requisitos extraídos:
{as_prompt_json(job.requirements or {})}

Descripción original (recortada):
---
{(job.description_raw or '')[:12000]}
---

CANDIDATO
{as_prompt_json(resume_data)}

SCORE DETERMINISTA YA CALCULADO
Cobertura de skills: {result.skill_score}% — coinciden {result.matched_skills}
Faltan: {result.missing_skills}
Similitud semántica: {result.semantic_score}%
Encaje de seniority: {result.seniority_score}%

Analiza el encaje."""

    return llm.extract(
        system=_ANALYSIS_SYSTEM,
        user=user,
        output_model=MatchAnalysis,
        max_tokens=10000,
    )


def upsert(db: Session, resume: Resume, job: Job, with_analysis: bool = False) -> MatchResult:
    """Calcula (y cachea) el match. El análisis LLM solo si se pide explícitamente."""
    result = compute(resume, job)

    row = db.scalar(
        select(JobMatch).where(JobMatch.resume_id == resume.id, JobMatch.job_id == job.id)
    )
    if row is None:
        row = JobMatch(resume_id=resume.id, job_id=job.id)
        db.add(row)

    row.score = result.score
    row.semantic_score = result.semantic_score
    row.skill_score = result.skill_score
    row.seniority_score = result.seniority_score
    row.matched_skills = result.matched_skills
    row.missing_skills = result.missing_skills

    if with_analysis and llm.available:
        try:
            analysis = analyze(resume, job)
            row.analysis = analysis.model_dump()
            result.analysis = analysis
        except LLMError:
            row.analysis = None
    elif row.analysis:
        result.analysis = MatchAnalysis.model_validate(row.analysis)

    db.flush()
    return result


def rank(db: Session, resume: Resume, jobs: list[Job]) -> dict[int, MatchResult]:
    """Puntúa un lote de vacantes contra un CV. Sin llamadas al LLM."""
    return {job.id: compute(resume, job) for job in jobs}
