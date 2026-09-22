"""Inteligencia por vacante: empresa, proceso de entrevista, salario, carta y checklist.

Lo que depende de información pública fresca (noticias, cómo entrevista una
empresa, rangos salariales) se resuelve con el server tool de búsqueda web de
Claude, y se devuelve siempre con `sources` y `confidence` para que el usuario
sepa cuánto fiarse. Lo que depende solo del CV y la oferta no busca nada.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import CompanyIntel, InterviewInsight, Job, Resume
from app.schemas.application import GeneratedTask, TaskPlan
from app.schemas.intel import (
    CompanyIntelData,
    CoverLetterDraft,
    InterviewIntelData,
    SalaryBenchmark,
)
from app.schemas.resume import ResumeData
from app.services.llm import as_prompt_json, llm

log = get_logger(__name__)

CACHE_TTL = timedelta(days=14)


def company_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


# --------------------------------------------------------------------------
# Empresa
# --------------------------------------------------------------------------
_COMPANY_SYSTEM = """Investigas empresas para un candidato que va a entrevistarse con ellas.

Busca en la web y recopila: a qué se dedica, tamaño, sector, stack tecnológico conocido,
producto, financiación y noticias de los últimos 12 meses.

Reglas:
- Distingue hechos de rumores. Si una empresa tiene nombre ambiguo, dilo en vez de mezclar
  información de dos empresas distintas.
- `talking_points`: hechos CONCRETOS y recientes que el candidato pueda mencionar para
  demostrar que investigó. Nada de "me gusta su cultura innovadora".
- `questions_to_ask`: preguntas que revelen criterio técnico y que no se respondan mirando
  la web de la empresa.
- `confidence`: high solo si encontraste fuentes primarias (web oficial, prensa seria).
Responde en español."""


def research_company(db: Session, company: str, force: bool = False) -> CompanyIntelData:
    key = company_key(company)
    row = db.scalar(select(CompanyIntel).where(CompanyIntel.company_key == key))

    fresh = (
        row is not None
        and row.refreshed_at is not None
        and datetime.now(timezone.utc) - row.refreshed_at < CACHE_TTL
    )
    if row is not None and fresh and not force:
        return CompanyIntelData.model_validate(row.data)

    data, sources = llm.research(
        system=_COMPANY_SYSTEM,
        user=f"Investiga la empresa '{company}'. Busca su web oficial, su perfil en LinkedIn "
        f"o Crunchbase, su stack tecnológico y noticias recientes.",
        output_model=CompanyIntelData,
    )
    data.company_name = data.company_name or company
    data.sources = list(dict.fromkeys([*data.sources, *sources]))[:20]

    if row is None:
        row = CompanyIntel(company_key=key, company_name=company)
        db.add(row)
    row.data = data.model_dump()
    row.refreshed_at = datetime.now(timezone.utc)
    db.flush()
    return data


# --------------------------------------------------------------------------
# Proceso de entrevista
# --------------------------------------------------------------------------
_INTERVIEW_SYSTEM = """Investigas cómo entrevista una empresa para un rol concreto.

Busca en la web experiencias de candidatos (Glassdoor, Blind, Reddit, foros, blogs) y la
página de carreras de la empresa.

Reglas:
- Reconstruye las ETAPAS del proceso en orden, con formato y duración cuando se sepa.
- `assessment_types`: sé específico — "LeetCode medium/hard en 45 min", "take-home de 4-6h",
  "system design", "psicotécnico", "STAR behavioral", "live coding con pair programming".
- `common_questions`: preguntas realmente reportadas, no inventadas. Si no encuentras
  ninguna específica de esta empresa, usa las típicas del ROL y dilo en `tips`.
- `technical_topics`: qué repasar concretamente para ESTA vacante, derivado de sus requisitos.
- `confidence`: low si solo encontraste información genérica del rol.
Responde en español."""


def research_interview_process(
    db: Session, company: str, role: str, job: Job | None = None, force: bool = False
) -> InterviewIntelData:
    ckey, rkey = company_key(company), company_key(role)
    row = db.scalar(
        select(InterviewInsight).where(
            InterviewInsight.company_key == ckey, InterviewInsight.role_key == rkey
        )
    )
    fresh = (
        row is not None
        and datetime.now(timezone.utc) - row.updated_at < CACHE_TTL
    )
    if row is not None and fresh and not force:
        return InterviewIntelData.model_validate(row.data)

    requirements = as_prompt_json(job.requirements) if job and job.requirements else "(no disponible)"
    data, sources = llm.research(
        system=_INTERVIEW_SYSTEM,
        user=(
            f"¿Cómo es el proceso de entrevista de '{company}' para el rol de '{role}'?\n"
            f"Busca experiencias de candidatos y la descripción oficial del proceso.\n\n"
            f"Requisitos de la vacante concreta:\n{requirements}"
        ),
        output_model=InterviewIntelData,
    )
    data.company_name = data.company_name or company
    data.role = data.role or role
    data.sources = list(dict.fromkeys([*data.sources, *sources]))[:20]

    if row is None:
        row = InterviewInsight(company_key=ckey, role_key=rkey)
        db.add(row)
    row.data = data.model_dump()
    db.flush()
    return data


# --------------------------------------------------------------------------
# Salario
# --------------------------------------------------------------------------
_SALARY_SYSTEM = """Estimas rangos salariales reales de mercado y preparas la negociación.

Busca en fuentes de compensación (Levels.fyi, Glassdoor, Payscale, informes locales, ofertas
comparables) para el rol, nivel y ubicación indicados.

Reglas:
- Da p25/p50/p75 en la moneda LOCAL de la ubicación, anual bruto salvo que la zona use otra
  convención (indícalo en `period`).
- Explica en `reasoning` de dónde sale el rango y qué tan sólido es. Si los datos son pobres,
  dilo y baja `confidence`.
- `negotiation_script`: frases literales que el candidato puede usar. Concretas, no consejos.
- `leverage_points`: qué de SU perfil justifica pedir la parte alta del rango.
Responde en español."""


def salary_benchmark(
    role: str, location: str, seniority: str = "", resume: Resume | None = None
) -> SalaryBenchmark:
    profile = ""
    if resume is not None:
        data = ResumeData.model_validate(resume.parsed or {})
        profile = (
            f"\n\nPerfil del candidato:\n"
            f"- Años de experiencia: {data.total_years_experience}\n"
            f"- Seniority: {data.detected_seniority}\n"
            f"- Stack: {', '.join(data.skills.flat()[:25])}"
        )

    benchmark, sources = llm.research(
        system=_SALARY_SYSTEM,
        user=(
            f"Rango salarial de mercado para '{role}'"
            f"{f' ({seniority})' if seniority else ''} en {location or 'remoto internacional'}."
            f"{profile}"
        ),
        output_model=SalaryBenchmark,
    )
    benchmark.role = benchmark.role or role
    benchmark.location = benchmark.location or location
    benchmark.sources = list(dict.fromkeys([*benchmark.sources, *sources]))[:20]
    return benchmark


# --------------------------------------------------------------------------
# Carta de presentación
# --------------------------------------------------------------------------
_COVER_SYSTEM = """Escribes cartas de presentación que un reclutador lee entera.

Reglas:
- 180-280 palabras. Cuatro párrafos como mucho. Nada de "Por la presente me dirijo a ustedes".
- Primer párrafo: por qué ESTA empresa y ESTE rol, con un dato concreto que demuestre
  investigación real. Si no tienes información de la empresa, ancla en el contenido de la oferta.
- Segundo y tercero: DOS proyectos o logros del CV que respondan directamente a los requisitos
  principales de la vacante, con la métrica si existe.
- Cierre breve y con iniciativa, sin súplicas ni "quedo a su entera disposición".
- Solo información que esté en el CV. Cero invenciones.
- Mismo idioma que la oferta.
- Prohibido: "apasionado por la tecnología", "proactivo", "sinergia", "valor agregado",
  "como se puede apreciar en mi currículum"."""


def cover_letter(
    resume: Resume, job: Job, company_data: CompanyIntelData | None = None, tone: str = "professional"
) -> CoverLetterDraft:
    data = ResumeData.model_validate(resume.parsed or {})
    intel_block = (
        f"\n\nInvestigación de la empresa:\n{as_prompt_json(company_data)}" if company_data else ""
    )

    draft = llm.extract(
        system=_COVER_SYSTEM,
        user=f"""VACANTE
Puesto: {job.title}
Empresa: {job.company}
Ubicación: {job.location or 'no indicada'}

Requisitos:
{as_prompt_json(job.requirements or {})}

Descripción:
{(job.description_raw or '')[:10000]}

CANDIDATO
{as_prompt_json(data)}{intel_block}

Tono: {tone}

Escribe la carta.""",
        output_model=CoverLetterDraft,
        max_tokens=6000,
    )
    draft.word_count = len(draft.body.split())
    return draft


# --------------------------------------------------------------------------
# Checklist de preparación
# --------------------------------------------------------------------------
_TASKS_SYSTEM = """Generas el plan de preparación de una postulación concreta.

Entre 6 y 10 tareas, cada una ejecutable en una sesión. Cubre estas categorías:
- study: temas técnicos concretos a repasar, derivados de los requisitos de ESTA vacante
  y de los gaps del candidato. Nada de "repasar algoritmos": di cuáles y por qué.
- storytelling: historias STAR específicas alineadas con lo que la empresa valora.
- networking: a quién contactar en LinkedIn y con qué ángulo.
- follow_up: seguimiento a los 5 y 10 días hábiles tras postular.
- logistics: portafolio, referencias, documentación.

`days_from_now` marca el vencimiento; 0 si no tiene fecha natural.
Responde en español."""


def generate_tasks(
    resume: Resume | None,
    job: Job,
    missing_skills: list[str] | None = None,
    interview_data: InterviewIntelData | None = None,
) -> list[GeneratedTask]:
    profile = ""
    if resume is not None:
        data = ResumeData.model_validate(resume.parsed or {})
        profile = f"\n\nPerfil del candidato:\n{as_prompt_json(data)}"

    process = (
        f"\n\nProceso de entrevista conocido:\n{as_prompt_json(interview_data)}"
        if interview_data
        else ""
    )

    plan = llm.extract(
        system=_TASKS_SYSTEM,
        user=f"""VACANTE
{job.title} en {job.company} ({job.location or 'no indicada'}, {job.remote_type})

Requisitos:
{as_prompt_json(job.requirements or {})}

Skills que le faltan al candidato: {', '.join(missing_skills or []) or 'ninguna detectada'}
{profile}{process}

Genera el plan de preparación.""",
        output_model=TaskPlan,
        effort="medium",
        max_tokens=8000,
    )
    return plan.tasks


def fallback_tasks(job: Job, missing_skills: list[str] | None = None) -> list[GeneratedTask]:
    """Checklist base cuando no hay API key. Genérico pero no inútil."""
    tasks = [
        GeneratedTask(
            title=f"Repasar los requisitos técnicos de {job.title}",
            detail="Lee la oferta línea por línea y anota cada tecnología que no domines.",
            category="study",
            days_from_now=2,
        ),
        GeneratedTask(
            title=f"Investigar a {job.company}",
            detail="Producto, modelo de negocio, noticias del último año y stack público.",
            category="study",
            days_from_now=2,
        ),
        GeneratedTask(
            title="Preparar 2 historias STAR",
            detail="Una de impacto técnico medible y otra de conflicto o fallo que resolviste.",
            category="storytelling",
            days_from_now=3,
        ),
        GeneratedTask(
            title="Contactar a alguien del equipo en LinkedIn",
            detail="Busca ingenieros del área o al reclutador. Mensaje corto, con una pregunta real.",
            category="networking",
            days_from_now=3,
        ),
        GeneratedTask(
            title="Follow-up a los 5 días hábiles",
            detail="Correo breve reiterando interés y aportando un dato nuevo sobre tu perfil.",
            category="follow_up",
            days_from_now=7,
        ),
        GeneratedTask(
            title="Follow-up a los 10 días hábiles",
            detail="Último recordatorio. Si no hay respuesta, cierra la postulación y sigue.",
            category="follow_up",
            days_from_now=14,
        ),
    ]
    for skill in (missing_skills or [])[:3]:
        tasks.insert(
            0,
            GeneratedTask(
                title=f"Cubrir gap: {skill}",
                detail=f"Haz un mini-proyecto o tutorial de {skill} para poder hablarlo con criterio.",
                category="study",
                days_from_now=4,
            ),
        )
    return tasks
