"""Plan de búsqueda de vacantes a partir de un CV.

Las bolsas globales están en inglés y buscan por título de puesto, así que un
CV en español ("Diseñadora Gráfica", "Estudiante de Ingeniería...") no sirve
tal cual como consulta. Claude lo traduce a 2-4 títulos realistas y deduce el
país de residencia; sin API key se cae a una heurística con los campos del CV.

El usuario ve el plan y lo puede corregir: la última versión que usó para cada
CV se guarda en las preferencias del perfil y tiene prioridad la próxima vez.
"""

from __future__ import annotations

import re

from app.core.logging import get_logger
from app.models import Resume, User
from app.schemas.job import SearchPlan, SearchTerms
from app.schemas.resume import ResumeData
from app.services import geo
from app.services.llm import LLMError, as_prompt_json, llm

log = get_logger(__name__)

_PLAN_SYSTEM = """Preparas búsquedas de empleo en bolsas internacionales en inglés
(Himalayas, Jobicy, Remotive) a partir de un CV.

Reglas:
- Propón títulos de puesto que la persona podría conseguir HOY con su experiencia real.
  Un estudiante con experiencia de soporte IT no es "Senior Software Engineer".
- Títulos cortos y estándar del mercado, en inglés: son las palabras que usan las ofertas.
- Varía el ángulo: el rol principal, un sinónimo frecuente y, si aplica, un rol adyacente.
- El país sale de la ubicación del contacto; si solo hay ciudad o región, dedúcelo."""

_PHONE_PREFIX = {
    "+57": "Colombia", "+52": "Mexico", "+34": "Spain", "+54": "Argentina", "+56": "Chile",
    "+51": "Peru", "+593": "Ecuador", "+58": "Venezuela", "+598": "Uruguay", "+55": "Brazil",
    "+506": "Costa Rica", "+507": "Panama", "+502": "Guatemala",
}

# (resume_id, updated_at) -> plan. Evita repetir la llamada al abrir el modal varias veces.
_cache: dict[tuple[int, str], SearchPlan] = {}


def _pref_key(resume_id: int) -> str:
    return f"job_search:{resume_id}"


def detect_resume_country(data: ResumeData) -> str:
    country = geo.detect_country(data.contact.location)
    if country:
        return country
    phone = (data.contact.phone or "").replace(" ", "")
    for prefix in sorted(_PHONE_PREFIX, key=len, reverse=True):
        if phone.startswith(prefix):
            return _PHONE_PREFIX[prefix]
    return ""


def heuristic_queries(data: ResumeData, target_role: str | None) -> list[str]:
    candidates: list[str] = []
    if target_role:
        candidates.append(target_role)
    if data.contact.headline:
        # "Computer Engineering Student & Automation Technologist" -> dos consultas
        candidates += re.split(r"\s*(?:&|\||/|,|·| - )\s*", data.contact.headline)
    candidates += [e.role for e in data.experience[:2]]
    seen: list[str] = []
    for c in candidates:
        c = c.strip()
        if 2 < len(c) <= 60 and c.lower() not in (s.lower() for s in seen):
            seen.append(c)
    return seen[:3]


def build_plan(resume: Resume, user: User, use_llm: bool = True) -> SearchPlan:
    data = ResumeData.model_validate(resume.parsed or {})

    saved = (user.preferences or {}).get(_pref_key(resume.id))
    if isinstance(saved, dict) and saved.get("queries"):
        country = saved.get("country", "")
        return SearchPlan(
            resume_id=resume.id,
            queries=list(saved["queries"]),
            country=country,
            region=geo.region_of(country),
            origin="saved",
        )

    key = (resume.id, str(resume.updated_at))
    if key in _cache:
        return _cache[key]

    plan = SearchPlan(
        resume_id=resume.id,
        queries=heuristic_queries(data, resume.target_role),
        country=detect_resume_country(data),
    )
    if use_llm and llm.available:
        profile = {
            "headline": data.contact.headline,
            "location": data.contact.location,
            "phone": data.contact.phone,
            "target_role": resume.target_role or "",
            "summary": data.summary[:800],
            "seniority": data.detected_seniority,
            "years": data.total_years_experience,
            "experience": [
                {"role": e.role, "company": e.company, "start": e.start_date, "end": e.end_date}
                for e in data.experience[:6]
            ],
            "skills": data.skills.flat()[:25],
            "education": [f"{e.degree} {e.field_of_study}".strip() for e in data.education[:3]],
        }
        try:
            terms = llm.extract(
                system=_PLAN_SYSTEM,
                user=f"CV resumido:\n{as_prompt_json(profile)}",
                output_model=SearchTerms,
                effort="low",
                max_tokens=2000,
                cache_system=False,
            )
            if terms.queries:
                plan.queries = [q.strip() for q in terms.queries if q.strip()][:4]
                plan.origin = "ai"
            plan.country = geo.canonical(terms.country) or plan.country
        except LLMError as exc:
            log.warning("Plan de búsqueda con IA falló (%s); uso la heurística.", exc)

    plan.region = geo.region_of(plan.country)
    _cache[key] = plan
    return plan


def remember_plan(user: User, resume_id: int, queries: list[str], country: str) -> None:
    """Guarda en el perfil la última búsqueda usada para ese CV."""
    prefs = dict(user.preferences or {})
    prefs[_pref_key(resume_id)] = {"queries": queries, "country": country}
    user.preferences = prefs


def forget_plan(user: User, resume_id: int) -> None:
    prefs = dict(user.preferences or {})
    prefs.pop(_pref_key(resume_id), None)
    user.preferences = prefs
