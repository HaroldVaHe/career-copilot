"""Adaptación del CV a una vacante, con diff palabra a palabra estilo Git.

Principio de diseño: el sistema nunca guarda una reescritura por su cuenta.
Genera la propuesta, la muestra como diff, marca lo que podría ser una invención,
y el usuario decide qué acepta. Un CV con una afirmación falsa no es un CV
optimizado, es un problema en la entrevista técnica.
"""

from __future__ import annotations

import difflib
import re

from sqlalchemy.orm import Session

from app.models import Job, Resume
from app.schemas.io import (
    BulletDiff,
    DiffLine,
    SaveVariantRequest,
    TailoredResumeDraft,
    TailorResponse,
)
from app.schemas.resume import ResumeData
from app.services.embeddings import embed
from app.services.llm import as_prompt_json, llm
from app.services.resume import embedding_text
from app.services.taxonomy import extract_skills

_TOKEN_SPLIT = re.compile(r"(\s+)")

_TAILOR_SYSTEM = """Adaptas un CV existente a una vacante concreta.

Reglas absolutas:
1. VERACIDAD. No puedes añadir tecnologías, responsabilidades, métricas ni empleos que no
   estén en el CV original. Reformular sí; inventar no.
2. Si una reescritura introduce cualquier dato que no estaba en el original, marca
   `invented_facts: true` y explica en `warnings` qué debe verificar el usuario.
3. Reordena y reencuadra: sube al frente lo que la vacante pide, baja lo irrelevante,
   usa el vocabulario literal de la oferta cuando el candidato tenga base real para ello
   (ej. si el CV dice "APIs con Flask" y la oferta pide "servicios REST", di "servicios REST").
4. Cada bullet reescrito sigue la fórmula X-Y-Z: "Logré [X] medido por [Y] haciendo [Z]".
   Si el original no tiene métrica, deja un placeholder entre corchetes — jamás un número inventado.
5. Máximo 10 bullets reescritos: los que más muevan la aguja.
6. Escribe en el mismo idioma del CV original.
7. `added_keywords`: términos de la oferta que has conseguido incorporar con honestidad."""

_INJECT_NOTE = """
MODO INYECCIÓN DE GAPS ACTIVADO: el usuario pide integrar explícitamente las tecnologías que
la oferta exige y el CV no menciona. Hazlo SOLO donde sea plausible que el candidato las haya
usado dado su stack (ej. si usó PostgreSQL, es plausible que escribiera SQL). Cada una de esas
reescrituras lleva OBLIGATORIAMENTE `invented_facts: true` y una entrada en `warnings`."""


def word_diff(before: str, after: str) -> list[DiffLine]:
    """Diff a nivel de palabra, listo para pintar en verde/rojo."""
    a = [t for t in _TOKEN_SPLIT.split(before or "") if t]
    b = [t for t in _TOKEN_SPLIT.split(after or "") if t]

    lines: list[DiffLine] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            lines.append(DiffLine(kind="equal", text="".join(a[i1:i2])))
        elif tag == "delete":
            lines.append(DiffLine(kind="delete", text="".join(a[i1:i2])))
        elif tag == "insert":
            lines.append(DiffLine(kind="insert", text="".join(b[j1:j2])))
        else:  # replace
            lines.append(DiffLine(kind="delete", text="".join(a[i1:i2])))
            lines.append(DiffLine(kind="insert", text="".join(b[j1:j2])))
    return [line for line in lines if line.text]


def tailor(
    resume: Resume,
    job: Job | None,
    job_description: str | None = None,
    inject_gaps: bool = False,
    tone: str = "professional",
) -> TailorResponse:
    data = ResumeData.model_validate(resume.parsed or {})

    if job is not None:
        job_block = (
            f"Título: {job.title}\nEmpresa: {job.company}\n"
            f"Seniority: {job.seniority or 'no indicado'}\n\n"
            f"Requisitos extraídos:\n{as_prompt_json(job.requirements or {})}\n\n"
            f"Descripción:\n{(job.description_raw or '')[:12000]}"
        )
        job_text = job.description_raw or ""
    else:
        job_block = f"Descripción de la oferta:\n{(job_description or '')[:12000]}"
        job_text = job_description or ""

    have = {s.lower() for s in data.skills.flat()}
    gaps = [s for s in extract_skills(job_text) if s.lower() not in have]

    system = _TAILOR_SYSTEM + (_INJECT_NOTE if inject_gaps else "")
    user = f"""VACANTE
{job_block}

CV ACTUAL (estructurado)
{as_prompt_json(data)}

Tecnologías que pide la oferta y no aparecen en el CV: {', '.join(gaps[:20]) or 'ninguna'}
Tono pedido: {tone}

Adapta el CV. Los índices de `bullets` apuntan a la lista `experience` (0-based) y a la
posición dentro de `bullets` de ese rol."""

    draft = llm.extract(
        system=system,
        user=user,
        output_model=TailoredResumeDraft,
        max_tokens=16000,
    )

    bullet_diffs: list[BulletDiff] = []
    for item in draft.bullets:
        exp_idx, bul_idx = item.experience_index, item.bullet_index
        if not (0 <= exp_idx < len(data.experience)):
            continue
        exp = data.experience[exp_idx]
        original = exp.bullets[bul_idx] if 0 <= bul_idx < len(exp.bullets) else ""
        bullet_diffs.append(
            BulletDiff(
                experience_index=exp_idx,
                bullet_index=bul_idx,
                company=exp.company,
                role=exp.role,
                original=original,
                suggestion=item.suggestion,
                rationale=item.rationale,
                invented_facts=item.invented_facts,
                words=word_diff(original, item.suggestion),
            )
        )

    warnings = list(draft.warnings)
    flagged = sum(1 for d in bullet_diffs if d.invented_facts)
    if flagged:
        warnings.insert(
            0,
            f"{flagged} sugerencia(s) añaden información que no estaba en tu CV. "
            "Revísalas una por una: solo acéptalas si son ciertas.",
        )

    return TailorResponse(
        resume_id=resume.id,
        job_id=job.id if job else None,
        summary_before=data.summary,
        summary_after=draft.summary,
        summary_diff=word_diff(data.summary, draft.summary),
        bullet_diffs=bullet_diffs,
        added_keywords=draft.added_keywords,
        warnings=warnings,
    )


def save_variant(db: Session, resume: Resume, payload: SaveVariantRequest) -> Resume:
    """Crea una versión del CV con solo los cambios que el usuario aceptó."""
    data = ResumeData.model_validate(resume.parsed or {})

    if payload.accepted_summary is not None:
        data.summary = payload.accepted_summary

    for accepted in payload.accepted_bullets:
        idx, bullet_idx = accepted.experience_index, accepted.bullet_index
        if 0 <= idx < len(data.experience):
            bullets = data.experience[idx].bullets
            if 0 <= bullet_idx < len(bullets):
                bullets[bullet_idx] = accepted.suggestion
            elif accepted.suggestion:
                bullets.append(accepted.suggestion)

    variant = Resume(
        user_id=resume.user_id,
        label=payload.label,
        target_role=payload.target_role or resume.target_role,
        source_filename=resume.source_filename,
        raw_text=_render_text(data),
        parsed=data.model_dump(),
        parent_id=resume.id,
        tailored_for_job_id=payload.job_id,
        is_primary=False,
    )
    variant.embedding = embed(embedding_text(data, variant.raw_text))

    db.add(variant)
    db.flush()
    return variant


def _render_text(data: ResumeData) -> str:
    """Reconstruye un CV en texto plano desde la estructura — útil para
    re-scorear la variante y para copiar/pegar."""
    lines: list[str] = []
    c = data.contact
    if c.full_name:
        lines.append(c.full_name)
    if c.headline:
        lines.append(c.headline)
    contact_bits = [c.email, c.phone, c.location, c.linkedin, c.github]
    if any(contact_bits):
        lines.append(" | ".join(b for b in contact_bits if b))

    if data.summary:
        lines += ["", "RESUMEN PROFESIONAL", data.summary]

    if data.experience:
        lines += ["", "EXPERIENCIA"]
        for exp in data.experience:
            period = f"{exp.start_date} - {'Presente' if exp.is_current else exp.end_date}".strip(" -")
            lines.append(f"{exp.role} — {exp.company} ({period})")
            lines += [f"• {b}" for b in exp.bullets]
            if exp.technologies:
                lines.append(f"Tecnologías: {', '.join(exp.technologies)}")
            lines.append("")

    if data.skills.flat():
        lines += ["STACK TÉCNICO", ", ".join(data.skills.flat())]

    if data.education:
        lines += ["", "EDUCACIÓN"]
        for edu in data.education:
            lines.append(
                f"{edu.degree} {edu.field_of_study} — {edu.institution} "
                f"({edu.start_date} - {edu.end_date})".strip()
            )

    if data.certifications:
        lines += ["", "CERTIFICACIONES"]
        lines += [f"{cert.name} — {cert.issuer} ({cert.date})".strip(" —()") for cert in data.certifications]

    if data.projects:
        lines += ["", "PROYECTOS"]
        for project in data.projects:
            lines.append(f"{project.name}: {project.description}")

    if data.languages:
        lines += ["", "IDIOMAS", ", ".join(f"{lang.language} ({lang.level})" for lang in data.languages)]

    return "\n".join(lines).strip()
