"""Auditoría ATS: mitad determinista, mitad juicio del modelo.

Lo medible se mide en Python (formato, cuantificación, densidad de keywords,
secciones ausentes) porque tiene que ser reproducible y gratis. Lo que requiere
criterio — si un bullet realmente vende, si el perfil encaja con el rol — se le
pide a Claude, y la nota final es la mezcla de ambos.
"""

from __future__ import annotations

import re

from app.schemas.ats import (
    AtsFinding,
    AtsLlmReview,
    AtsReport,
    AtsScoreBreakdown,
    BulletRewrite,
)
from app.schemas.resume import ResumeData
from app.services.documents import DocumentSignals
from app.services.llm import LLMError, as_prompt_json, llm
from app.services.taxonomy import extract_skills

# Un CV sólido de perfil técnico suele exponer entre 12 y 18 tecnologías distintas.
SKILL_TARGET = 15

_NUMBER_RE = re.compile(
    r"(\d+[\d.,]*\s*(%|k\b|m\b|mil\b|millones?\b|usd|eur|€|\$|x\b|h\b|hrs?\b|días?\b|meses?\b))"
    r"|(\b\d{2,}\b)",
    re.IGNORECASE,
)

_ACTION_VERBS = {
    # español
    "lideré", "desarrollé", "implementé", "diseñé", "optimicé", "reduje", "aumenté",
    "automaticé", "migré", "construí", "creé", "mejoré", "coordiné", "gestioné",
    "analicé", "integré", "desplegué", "refactoricé", "escalé", "entregué", "definí",
    # inglés
    "led", "built", "developed", "implemented", "designed", "optimized", "reduced",
    "increased", "automated", "migrated", "created", "improved", "managed", "delivered",
    "architected", "scaled", "launched", "shipped", "refactored", "owned", "drove",
}

_WEAK_OPENERS = {
    "responsable", "encargado", "encargada", "participé", "ayudé", "apoyé", "colaboré",
    "responsible", "helped", "assisted", "worked", "participated", "involved",
}

WEIGHTS = {
    "technical_relevance": 0.25,
    "clarity_format": 0.20,
    "achievement_quantification": 0.25,
    "skill_coverage": 0.15,
    "ats_parseability": 0.15,
}

_AUDIT_SYSTEM = """Eres un revisor técnico de CVs con experiencia real en reclutamiento IT y en
cómo se comportan los ATS (Workday, Greenhouse, Lever, Taleo).

Evalúas tres ejes de 0 a 100:
- technical_relevance: ¿el stack y la experiencia son coherentes y demandados para el rol objetivo?
- clarity_format: ¿se lee rápido? Jerarquía, longitud de bullets, ausencia de relleno.
- achievement_quantification: ¿los bullets muestran impacto medido, o solo describen tareas?

Reglas innegociables:
1. NUNCA inventes datos. Si un bullet no tiene métrica, propón la estructura con un
   placeholder explícito entre corchetes, p. ej. "reduciendo el tiempo de carga un [X]%".
   Marca `invented_facts: true` en cualquier sugerencia que añada algo que no estaba.
2. Cada reescritura sigue la fórmula X-Y-Z de Google: "Logré [X] medido por [Y] haciendo [Z]".
3. Sé específico y accionable. "Mejora el formato" no sirve; "junta las dos columnas en
   una sola, los ATS leen el PDF en orden equivocado" sí.
4. Propón como máximo 8 reescrituras: las de mayor impacto.
5. Responde en el mismo idioma en el que está escrito el CV."""


def analyze(
    resume: ResumeData,
    raw_text: str,
    signals: DocumentSignals | None = None,
    target_role: str | None = None,
    use_llm: bool = True,
) -> AtsReport:
    """Informe ATS completo. Si el LLM no está disponible, cae a la parte determinista."""
    signals = signals or DocumentSignals(words=len(raw_text.split()))

    keyword_density = extract_skills(raw_text)
    findings: list[AtsFinding] = []

    parseability = _score_parseability(signals, findings)
    coverage = _score_coverage(keyword_density, findings)
    quantification, bullet_stats = _score_quantification(resume, findings)
    clarity = _score_clarity(resume, raw_text, signals, findings)
    relevance = _score_relevance(resume, keyword_density, findings)

    missing = _missing_sections(resume, findings)
    strengths = _strengths(resume, keyword_density, bullet_stats)
    rewrites: list[BulletRewrite] = []
    quick_wins: list[str] = []

    if use_llm and llm.available:
        try:
            review = _llm_review(resume, raw_text, target_role, keyword_density)
            # La mezcla evita dos fallos opuestos: el heurístico es ciego al
            # contenido, y el modelo es generoso si se le deja solo.
            relevance = _blend(relevance, review.technical_relevance)
            clarity = _blend(clarity, review.clarity_format)
            quantification = _blend(quantification, review.achievement_quantification)
            findings.extend(review.findings)
            rewrites = review.rewrites
            strengths = review.strengths or strengths
            quick_wins = review.quick_wins
        except LLMError as exc:
            findings.append(
                AtsFinding(
                    severity="info",
                    area="análisis",
                    message="La revisión con IA no se pudo completar.",
                    fix=str(exc),
                )
            )

    breakdown = AtsScoreBreakdown(
        technical_relevance=round(relevance, 1),
        clarity_format=round(clarity, 1),
        achievement_quantification=round(quantification, 1),
        skill_coverage=round(coverage, 1),
        ats_parseability=round(parseability, 1),
    )
    overall = sum(getattr(breakdown, key) * weight for key, weight in WEIGHTS.items())

    if not quick_wins:
        quick_wins = _fallback_quick_wins(findings)

    order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: order.get(f.severity, 3))

    return AtsReport(
        overall_score=round(overall, 1),
        breakdown=breakdown,
        findings=findings,
        rewrites=rewrites,
        keyword_density=dict(list(keyword_density.items())[:40]),
        missing_sections=missing,
        strengths=strengths,
        quick_wins=quick_wins[:5],
    )


def _blend(deterministic: float, model_score: float) -> float:
    if model_score <= 0:
        return deterministic
    return deterministic * 0.4 + model_score * 0.6


# --------------------------------------------------------------------------
# Ejes deterministas
# --------------------------------------------------------------------------
def _score_parseability(signals: DocumentSignals, findings: list[AtsFinding]) -> float:
    score = 100.0

    if not signals.has_text_layer:
        score -= 60
        findings.append(
            AtsFinding(
                severity="critical",
                area="formato",
                message="El PDF no tiene capa de texto: parece un escaneo o una imagen.",
                fix="Exporta el CV a PDF desde el editor original (Word, Docs, LaTeX), no lo escanees.",
            )
        )
    if signals.likely_multicolumn:
        score -= 22
        findings.append(
            AtsFinding(
                severity="critical",
                area="formato",
                message="Diseño a dos columnas detectado.",
                fix="Pásalo a una sola columna. Muchos ATS leen las columnas intercaladas y "
                "destrozan el orden de tu experiencia.",
            )
        )
    if signals.tables > 0:
        score -= min(18, 6 * signals.tables)
        findings.append(
            AtsFinding(
                severity="warning",
                area="formato",
                message=f"{signals.tables} tabla(s) en el documento.",
                fix="Sustituye las tablas por texto con bullets; varios parsers las ignoran por completo.",
            )
        )
    if signals.images > 2:
        score -= 8
        findings.append(
            AtsFinding(
                severity="info",
                area="formato",
                message=f"{signals.images} imágenes detectadas.",
                fix="Iconos y gráficos no se parsean. Asegúrate de que ningún dato viva solo dentro de una imagen.",
            )
        )
    if len(signals.distinct_fonts) > 3:
        score -= 6
        findings.append(
            AtsFinding(
                severity="info",
                area="formato",
                message=f"{len(signals.distinct_fonts)} familias tipográficas distintas.",
                fix="Limítate a una o dos fuentes estándar.",
            )
        )
    if signals.pages > 2:
        score -= 12
        findings.append(
            AtsFinding(
                severity="warning",
                area="formato",
                message=f"El CV ocupa {signals.pages} páginas.",
                fix="Recorta a 1 página (menos de 8 años de experiencia) o 2 como máximo.",
            )
        )
    if signals.words and signals.words < 200:
        score -= 15
        findings.append(
            AtsFinding(
                severity="warning",
                area="contenido",
                message=f"Solo {signals.words} palabras: el CV está muy vacío.",
                fix="Desarrolla cada experiencia con 3-5 bullets de impacto.",
            )
        )
    return max(0.0, min(100.0, score))


def _score_coverage(keyword_density: dict[str, int], findings: list[AtsFinding]) -> float:
    distinct = len(keyword_density)
    score = min(100.0, (distinct / SKILL_TARGET) * 100)
    if distinct < 6:
        findings.append(
            AtsFinding(
                severity="critical",
                area="keywords",
                message=f"Solo se reconocieron {distinct} tecnologías en todo el CV.",
                fix="Añade una sección 'Stack técnico' y nombra las herramientas dentro de cada "
                "experiencia: el ATS busca literales, no intenciones.",
            )
        )
    elif distinct < 10:
        findings.append(
            AtsFinding(
                severity="warning",
                area="keywords",
                message=f"{distinct} tecnologías reconocidas; lo habitual en un perfil competitivo son 12-18.",
                fix="Revisa que cada proyecto mencione su stack concreto.",
            )
        )
    return score


def _score_quantification(
    resume: ResumeData, findings: list[AtsFinding]
) -> tuple[float, dict[str, int]]:
    bullets = [b for exp in resume.experience for b in exp.bullets if b.strip()]
    stats = {"total": len(bullets), "quantified": 0, "strong_verb": 0, "weak_opener": 0}

    if not bullets:
        findings.append(
            AtsFinding(
                severity="critical",
                area="cuantificación",
                message="No se detectaron bullets de logros en la experiencia.",
                fix="Cada rol necesita 3-5 bullets. Empieza por un verbo de acción y cierra con el impacto.",
            )
        )
        return 0.0, stats

    for bullet in bullets:
        if _NUMBER_RE.search(bullet):
            stats["quantified"] += 1
        first = bullet.strip().lstrip("•-–* ").split(" ")[0].lower().strip(".,:")
        if first in _ACTION_VERBS:
            stats["strong_verb"] += 1
        elif first in _WEAK_OPENERS:
            stats["weak_opener"] += 1

    quantified_ratio = stats["quantified"] / stats["total"]
    verb_ratio = stats["strong_verb"] / stats["total"]
    score = quantified_ratio * 70 + verb_ratio * 30

    if quantified_ratio < 0.3:
        findings.append(
            AtsFinding(
                severity="critical",
                area="cuantificación",
                message=f"Solo {stats['quantified']} de {stats['total']} bullets contienen una métrica.",
                fix="Apunta a que al menos la mitad lleve número: %, tiempo ahorrado, usuarios, "
                "requests/s, tamaño de equipo, ingresos.",
            )
        )
    if stats["weak_opener"] > 0:
        findings.append(
            AtsFinding(
                severity="warning",
                area="redacción",
                message=f"{stats['weak_opener']} bullet(s) empiezan con fórmulas pasivas "
                "('responsable de', 'ayudé a').",
                fix="Cámbialas por un verbo de acción en primera persona: lideré, automaticé, reduje.",
            )
        )
    return min(100.0, score), stats


def _score_clarity(
    resume: ResumeData, raw_text: str, signals: DocumentSignals, findings: list[AtsFinding]
) -> float:
    score = 100.0
    contact = resume.contact

    missing_contact = [
        label
        for label, value in (
            ("email", contact.email),
            ("teléfono", contact.phone),
            ("ubicación", contact.location),
            ("LinkedIn", contact.linkedin),
        )
        if not value.strip()
    ]
    if missing_contact:
        score -= min(25, 7 * len(missing_contact))
        findings.append(
            AtsFinding(
                severity="warning" if "email" not in missing_contact else "critical",
                area="contacto",
                message=f"Faltan datos de contacto: {', '.join(missing_contact)}.",
                fix="Ponlos en la cabecera como texto plano, nunca solo dentro de un icono o imagen.",
            )
        )

    bullets = [b for exp in resume.experience for b in exp.bullets if b.strip()]
    if bullets:
        long_bullets = sum(1 for b in bullets if len(b.split()) > 32)
        if long_bullets > len(bullets) * 0.3:
            score -= 15
            findings.append(
                AtsFinding(
                    severity="warning",
                    area="redacción",
                    message=f"{long_bullets} bullets superan las 32 palabras.",
                    fix="Corta en una o dos líneas. Un reclutador dedica ~7 segundos al primer barrido.",
                )
            )

    if not resume.summary.strip():
        score -= 10
        findings.append(
            AtsFinding(
                severity="info",
                area="estructura",
                message="No hay resumen profesional.",
                fix="Añade 2-3 líneas arriba con rol, años de experiencia y stack principal. "
                "Es el gancho que decide si siguen leyendo.",
            )
        )

    if signals.bullet_chars == 0 and bullets:
        score -= 5

    return max(0.0, min(100.0, score))


def _score_relevance(
    resume: ResumeData, keyword_density: dict[str, int], findings: list[AtsFinding]
) -> float:
    """Proxy determinista: ¿las tecnologías aparecen dentro de la experiencia,
    o solo listadas en una sección suelta?"""
    experience_text = " ".join(
        b for exp in resume.experience for b in [*exp.bullets, exp.role, *exp.technologies]
    )
    in_experience = extract_skills(experience_text)

    if not keyword_density:
        return 20.0

    grounded = len(in_experience) / max(1, len(keyword_density))
    score = 40 + grounded * 50

    if resume.total_years_experience > 0:
        score += min(10, resume.total_years_experience)

    orphan = [s for s in keyword_density if s not in in_experience]
    if len(orphan) > 5:
        findings.append(
            AtsFinding(
                severity="warning",
                area="relevancia",
                message=f"{len(orphan)} tecnologías aparecen solo en la lista de skills, "
                "sin respaldo en ninguna experiencia.",
                fix=f"Ancla las que de verdad usaste ({', '.join(orphan[:5])}) dentro de un "
                "bullet concreto. Una skill sin contexto no convence a nadie.",
            )
        )
    return max(0.0, min(100.0, score))


def _missing_sections(resume: ResumeData, findings: list[AtsFinding]) -> list[str]:
    missing = []
    if not resume.experience:
        missing.append("experiencia")
    if not resume.education:
        missing.append("educación")
    if not resume.skills.flat():
        missing.append("habilidades técnicas")
    if not resume.summary.strip():
        missing.append("resumen profesional")
    if not resume.projects and len(resume.experience) < 2:
        missing.append("proyectos")

    if "experiencia" in missing:
        findings.append(
            AtsFinding(
                severity="critical",
                area="estructura",
                message="No se detectó una sección de experiencia laboral.",
                fix="Usa el encabezado literal 'Experiencia' o 'Experience'. Encabezados creativos "
                "('Mi trayectoria') confunden al parser.",
            )
        )
    return missing


def _strengths(
    resume: ResumeData, keyword_density: dict[str, int], bullet_stats: dict[str, int]
) -> list[str]:
    out = []
    if len(keyword_density) >= 12:
        out.append(f"Stack amplio y bien nombrado ({len(keyword_density)} tecnologías reconocidas).")
    if bullet_stats.get("total") and bullet_stats["quantified"] / bullet_stats["total"] >= 0.5:
        out.append("Más de la mitad de los logros están cuantificados.")
    if resume.total_years_experience >= 3:
        out.append(f"{resume.total_years_experience:.0f} años de experiencia acreditada.")
    if resume.certifications:
        out.append(f"{len(resume.certifications)} certificación(es) que respaldan el perfil.")
    return out


def _fallback_quick_wins(findings: list[AtsFinding]) -> list[str]:
    return [f.fix for f in findings if f.severity in ("critical", "warning") and f.fix][:5]


# --------------------------------------------------------------------------
# Revisión con Claude
# --------------------------------------------------------------------------
def _llm_review(
    resume: ResumeData,
    raw_text: str,
    target_role: str | None,
    keyword_density: dict[str, int],
) -> AtsLlmReview:
    role_line = f"Rol objetivo del candidato: {target_role}" if target_role else (
        "El candidato no ha fijado un rol objetivo; deduce el más plausible del propio CV."
    )
    user = f"""{role_line}

Tecnologías detectadas automáticamente (skill -> nº de menciones):
{as_prompt_json(dict(list(keyword_density.items())[:40]))}

CV estructurado:
{as_prompt_json(resume)}

Texto original del CV (para juzgar redacción y formato):
---
{raw_text[:14000]}
---

Audita este CV. Los índices de `rewrites` deben apuntar a la lista `experience` del
CV estructurado (0-based) y a la posición del bullet dentro de `bullets`."""

    return llm.extract(
        system=_AUDIT_SYSTEM,
        user=user,
        output_model=AtsLlmReview,
        max_tokens=16000,
    )
