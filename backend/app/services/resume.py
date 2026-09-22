"""Ingesta de CV: archivo -> texto -> JSON estructurado -> informe ATS."""

from __future__ import annotations

import re
from datetime import date

from app.schemas.resume import ContactInfo, ResumeData, SkillSet
from app.services import ats as ats_service
from app.services.documents import DocumentSignals, ParsedDocument
from app.services.llm import LLMError, llm
from app.services.taxonomy import SKILL_ALIASES, detect_seniority, extract_skills, years_to_seniority

_EXTRACT_SYSTEM = """Extraes la información de un CV a JSON estructurado.

Reglas:
- Transcribe, no interpretes. Copia los bullets tal cual aparecen, sin reescribirlos
  ni resumirlos. Corrige solo errores evidentes de extracción de PDF (palabras partidas,
  guiones de corte de línea, espacios duplicados).
- Fechas en formato YYYY-MM cuando sea deducible; el trabajo actual lleva end_date "present".
- Clasifica cada tecnología en su categoría de `skills`. Si una tecnología aparece solo
  dentro de una experiencia, inclúyela igualmente en `skills` y en `technologies` de ese rol.
- `total_years_experience`: suma los periodos profesionales, sin contar solapamientos ni
  prácticas académicas. Si no hay fechas suficientes, pon 0.
- `detected_seniority`: dedúcelo de los títulos y de los años, no del tono del CV.
- Los campos que no aparezcan en el CV se quedan vacíos. NUNCA inventes datos de contacto,
  empresas, fechas ni métricas."""

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/[\w\-/%.]+", re.I)
_GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w\-/.]+", re.I)


def extract_resume(raw_text: str) -> ResumeData:
    """Texto plano del CV -> `ResumeData`. Sin API key, usa el extractor heurístico."""
    if not raw_text.strip():
        return ResumeData()
    if not llm.available:
        return heuristic_resume(raw_text)
    try:
        data = llm.extract(
            system=_EXTRACT_SYSTEM,
            user=f"Extrae este CV a JSON:\n\n---\n{raw_text[:40000]}\n---",
            output_model=ResumeData,
            max_tokens=24000,
        )
    except LLMError:
        return heuristic_resume(raw_text)

    return _post_process(data, raw_text)


def _post_process(data: ResumeData, raw_text: str) -> ResumeData:
    """Rellena lo que el modelo pueda haber dejado suelto, con datos deterministas."""
    detected = extract_skills(raw_text)
    known = {s.lower() for s in data.skills.flat()}
    for skill in detected:
        if skill.lower() not in known:
            data.skills.other.append(skill)

    if not data.contact.email:
        match = _EMAIL_RE.search(raw_text)
        data.contact.email = match.group(0) if match else ""
    if not data.contact.linkedin:
        match = _LINKEDIN_RE.search(raw_text)
        data.contact.linkedin = match.group(0) if match else ""
    if not data.contact.github:
        match = _GITHUB_RE.search(raw_text)
        data.contact.github = match.group(0) if match else ""

    if not data.total_years_experience:
        data.total_years_experience = _estimate_years(data)
    if not data.detected_seniority:
        from_title = detect_seniority(" ".join(e.role for e in data.experience))
        data.detected_seniority = from_title or years_to_seniority(data.total_years_experience)
    return data


def _estimate_years(data: ResumeData) -> float:
    """Suma de periodos a partir de las fechas YYYY-MM, sin descontar solapamientos."""
    months = 0
    today = date.today()
    for exp in data.experience:
        start = _parse_month(exp.start_date)
        if not start:
            continue
        end = today if (exp.is_current or exp.end_date.lower() in ("present", "actual", "")) else (
            _parse_month(exp.end_date) or today
        )
        months += max(0, (end.year - start.year) * 12 + (end.month - start.month))
    return round(months / 12, 1)


def _parse_month(value: str) -> date | None:
    if not value:
        return None
    match = re.search(r"(\d{4})[-/](\d{1,2})", value)
    if match:
        return date(int(match.group(1)), min(12, max(1, int(match.group(2)))), 1)
    match = re.search(r"\b(19|20)\d{2}\b", value)
    if match:
        return date(int(match.group(0)), 1, 1)
    return None


# --------------------------------------------------------------------------
# Extractor sin IA (funciona con ANTHROPIC_API_KEY vacía)
# --------------------------------------------------------------------------
_SECTION_HINTS = {
    "experience": ["experiencia", "experience", "trayectoria", "employment", "work history"],
    "education": ["educación", "educacion", "education", "formación", "formacion", "academic"],
    "skills": ["habilidades", "skills", "competencias", "stack", "tecnologías", "tecnologias"],
    "summary": ["resumen", "perfil", "summary", "profile", "about", "objetivo"],
}


def heuristic_resume(raw_text: str) -> ResumeData:
    """Extracción degradada: contacto por regex, skills por taxonomía, resumen por sección.

    No reconstruye la experiencia laboral — eso requiere el modelo. Sirve para que
    la app arranque y muestre algo útil sin API key.
    """
    data = ResumeData()
    lines = [line for line in raw_text.split("\n") if line.strip()]

    email = _EMAIL_RE.search(raw_text)
    phone = _PHONE_RE.search(raw_text)
    linkedin = _LINKEDIN_RE.search(raw_text)
    github = _GITHUB_RE.search(raw_text)

    data.contact = ContactInfo(
        full_name=lines[0].strip() if lines else "",
        headline=lines[1].strip() if len(lines) > 1 and len(lines[1]) < 80 else "",
        email=email.group(0) if email else "",
        phone=phone.group(0).strip() if phone else "",
        linkedin=linkedin.group(0) if linkedin else "",
        github=github.group(0) if github else "",
    )

    summary_lines = _section_lines(lines, _SECTION_HINTS["summary"])
    data.summary = " ".join(summary_lines[:5]).strip()

    detected = extract_skills(raw_text)
    data.skills = _bucket_skills(list(detected.keys()))
    data.detected_seniority = detect_seniority(raw_text)
    return data


def _section_lines(lines: list[str], hints: list[str]) -> list[str]:
    collected: list[str] = []
    capturing = False
    for line in lines:
        lowered = line.lower().strip(" :#-")
        if any(lowered.startswith(h) for h in hints):
            capturing = True
            continue
        if capturing:
            is_new_section = len(lowered) < 40 and any(
                lowered.startswith(h)
                for group in _SECTION_HINTS.values()
                for h in group
            )
            if is_new_section:
                break
            collected.append(line.strip())
    return collected


_CATEGORY_OF: dict[str, str] = {}


def _category_for(skill: str) -> str:
    """Mapea una skill canónica al bucket de `SkillSet`."""
    if not _CATEGORY_OF:
        buckets = {
            "languages": ["Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "C", "Go",
                          "Rust", "PHP", "Ruby", "Kotlin", "Swift", "Scala", "R", "SQL", "Bash",
                          "PowerShell", "MATLAB", "Dart", "Elixir"],
            "databases": ["PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "SQL Server",
                          "Oracle", "SQLite", "DynamoDB", "Cassandra", "Snowflake", "BigQuery",
                          "Redshift"],
            "cloud_devops": ["AWS", "Azure", "Google Cloud", "Docker", "Kubernetes", "Terraform",
                             "Ansible", "CI/CD", "Linux", "Nginx", "Prometheus", "Serverless",
                             "MLOps"],
            "tools": ["Git", "Agile", "Jira", "Figma", "Excel", "Power BI", "Tableau", "Looker",
                      "Selenium", "Testing", "QA", "Webpack"],
        }
        for bucket, skills in buckets.items():
            for skill_name in skills:
                _CATEGORY_OF[skill_name] = bucket
        for skill_name in SKILL_ALIASES:
            _CATEGORY_OF.setdefault(skill_name, "frameworks")
    return _CATEGORY_OF.get(skill, "other")


def _bucket_skills(skills: list[str]) -> SkillSet:
    result = SkillSet()
    for skill in skills:
        getattr(result, _category_for(skill)).append(skill)
    return result


# --------------------------------------------------------------------------
# Helpers de alto nivel
# --------------------------------------------------------------------------
def embedding_text(resume: ResumeData, raw_text: str = "") -> str:
    """Texto que representa el CV para el matching semántico.

    Se repiten las skills y los títulos porque son la señal que de verdad
    discrimina; el texto completo aporta contexto pero diluye."""
    skills = ", ".join(resume.skills.flat())
    roles = " ".join(f"{e.role} en {e.company}" for e in resume.experience)
    bullets = " ".join(b for e in resume.experience for b in e.bullets)
    return "\n".join(
        [
            resume.contact.headline,
            resume.summary,
            f"Skills: {skills}",
            f"Skills: {skills}",  # doble peso, a propósito
            f"Roles: {roles}",
            bullets,
            raw_text[:4000],
        ]
    )


def build_report(resume: ResumeData, raw_text: str, signals: DocumentSignals | None = None,
                 target_role: str | None = None):
    return ats_service.analyze(resume, raw_text, signals, target_role)


def signals_from_parsed(parsed: ParsedDocument) -> DocumentSignals:
    return parsed.signals
