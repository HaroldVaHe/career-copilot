"""Normalización, persistencia e ingesta de vacantes."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Job
from app.schemas.job import JobNormalized, JobRequirements, SkillRequirement
from app.services import geo
from app.services.embeddings import embed
from app.services.llm import LLMError, llm
from app.services.sources import REGISTRY, RawJob
from app.services.taxonomy import detect_seniority, extract_skills

log = get_logger(__name__)

_NORMALIZE_SYSTEM = """Normalizas ofertas de empleo a JSON estructurado.

Reglas:
- Extrae solo lo que dice la oferta. Si un dato no aparece, déjalo vacío o en 0.
- `hard_skills`: tecnologías y competencias técnicas concretas. `required: true` solo si la
  oferta las presenta como excluyentes ("imprescindible", "must have", "se requiere").
  Todo lo que esté bajo "valorable", "deseable", "plus" va con `required: false`.
- Usa el nombre canónico de cada tecnología: "JavaScript" no "JS", "PostgreSQL" no "postgres".
- `salary_min`/`salary_max` en la moneda que indique la oferta, sin convertir. Si da un
  único número, ponlo en ambos. Si no hay salario, 0.
- `remote_type`: remote solo si es 100% remoto; hybrid si pide ir algunos días; onsite si
  es presencial; unknown si la oferta no lo aclara.
- `red_flags`: señales objetivas de alerta — ausencia de salario, stack desproporcionado
  para el seniority pedido, lenguaje tipo "familia", "trabajamos bajo presión", "multitarea",
  pedir 5 años de una tecnología que tiene 3. No especules sobre la empresa."""


def analyze_job_text(text: str, title: str = "", company: str = "") -> JobNormalized:
    """Descripción cruda -> estructura. Sin API key, cae al extractor heurístico."""
    if not llm.available:
        return heuristic_job(text, title, company)
    try:
        result = llm.extract(
            system=_NORMALIZE_SYSTEM,
            user=(
                f"Título conocido: {title or '(desconocido)'}\n"
                f"Empresa conocida: {company or '(desconocida)'}\n\n"
                f"Descripción de la oferta:\n---\n{text[:30000]}\n---"
            ),
            output_model=JobNormalized,
            model=None,
            effort="medium",
            max_tokens=12000,
        )
    except LLMError as exc:
        log.warning("Normalización con IA falló (%s); usando heurística.", exc)
        return heuristic_job(text, title, company)

    result.title = result.title or title
    result.company = result.company or company
    if not result.seniority:
        result.seniority = detect_seniority(f"{result.title} {text[:2000]}")
    return result


_SALARY_RE = re.compile(
    r"(?P<cur>[$€£]|usd|eur|cop|mxn|ars|clp)?\s*(?P<low>\d{1,3}(?:[.,]\d{3})+|\d{2,7})"
    r"\s*(?:-|–|a|to|hasta)\s*(?P<cur2>[$€£])?\s*(?P<high>\d{1,3}(?:[.,]\d{3})+|\d{2,7})"
    r"\s*(?P<cur3>[$€£]|usd|eur|cop|mxn|ars|clp)?",
    re.IGNORECASE,
)


def heuristic_job(text: str, title: str = "", company: str = "") -> JobNormalized:
    """Normalización sin IA: skills por taxonomía, salario y modalidad por regex."""
    lowered = text.lower()
    skills = extract_skills(text)

    # "imprescindible React" / "must have: Python" -> requisito duro
    required_zone = ""
    for marker in ("requisito", "imprescindible", "must have", "required", "requirements"):
        idx = lowered.find(marker)
        if idx >= 0:
            required_zone += text[idx : idx + 1200]
    required_skills = set(extract_skills(required_zone)) if required_zone else set(skills)

    remote_type = "unknown"
    if any(w in lowered for w in ("100% remoto", "fully remote", "remote-first", "teletrabajo")):
        remote_type = "remote"
    elif any(w in lowered for w in ("híbrido", "hibrido", "hybrid")):
        remote_type = "hybrid"
    elif any(w in lowered for w in ("presencial", "on-site", "onsite", "in office")):
        remote_type = "onsite"
    elif "remote" in lowered or "remoto" in lowered:
        remote_type = "remote"

    salary_min = salary_max = 0.0
    currency = ""
    match = _SALARY_RE.search(text)
    if match:
        salary_min = _to_number(match.group("low"))
        salary_max = _to_number(match.group("high"))
        # La moneda puede ir delante del primer número, entre ambos o detrás.
        currency = (
            match.group("cur") or match.group("cur2") or match.group("cur3") or ""
        ).upper().replace("$", "USD").replace("€", "EUR").replace("£", "GBP")

    years = 0.0
    years_match = re.search(r"(\d+)\s*\+?\s*(años|years|yrs)", lowered)
    if years_match:
        years = float(years_match.group(1))

    return JobNormalized(
        title=title,
        company=company,
        remote_type=remote_type,
        seniority=detect_seniority(f"{title} {text[:2000]}"),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=currency,
        salary_period="year" if salary_min > 10000 else "",
        tags=list(skills)[:15],
        requirements=JobRequirements(
            hard_skills=[
                SkillRequirement(name=s, required=s in required_skills) for s in skills
            ],
            years_experience=years,
            seniority=detect_seniority(title or text[:500]),
        ),
    )


def _to_number(raw: str) -> float:
    cleaned = raw.replace(".", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def embedding_text(job: Job) -> str:
    """Representación de la vacante para el matching semántico."""
    reqs = job.requirements or {}
    hard = ", ".join(s.get("name", "") for s in reqs.get("hard_skills", []))
    responsibilities = " ".join(reqs.get("responsibilities", []))
    return "\n".join(
        [
            job.title,
            f"Skills: {hard}",
            f"Skills: {hard}",  # doble peso, igual que en el CV
            f"Seniority: {job.seniority or ''}",
            responsibilities,
            (job.description_raw or "")[:6000],
        ]
    )


# --------------------------------------------------------------------------
# Persistencia
# --------------------------------------------------------------------------
def upsert_job(db: Session, raw: RawJob, analyze: bool = True) -> tuple[Job, bool]:
    """Inserta o actualiza una vacante. Devuelve (job, created)."""
    existing = None
    if raw.external_id:
        existing = db.scalar(
            select(Job).where(Job.source == raw.source, Job.external_id == raw.external_id)
        )
    if existing is None and raw.url:
        existing = db.scalar(select(Job).where(Job.url == raw.url))

    if existing is not None:
        # Solo refrescamos lo que puede cambiar; no reanalizamos para no gastar tokens.
        existing.title = raw.title or existing.title
        existing.company = raw.company or existing.company
        if raw.description_raw and len(raw.description_raw) > len(existing.description_raw or ""):
            existing.description_raw = raw.description_raw
            existing.embedding = embed(embedding_text(existing))
        return existing, False

    job = Job(
        source=raw.source,
        external_id=raw.external_id or None,
        url=raw.url or None,
        title=raw.title,
        company=raw.company,
        location=raw.location or None,
        remote_type=raw.remote_type,
        employment_type=raw.employment_type or None,
        description_raw=raw.description_raw,
        tags=raw.tags,
        posted_at=raw.posted_at,
        requirements={},
    )

    text_for_analysis = raw.description_raw or raw.title
    normalized = (
        analyze_job_text(text_for_analysis, raw.title, raw.company)
        if analyze
        else heuristic_job(text_for_analysis, raw.title, raw.company)
    )
    _apply_normalized(job, normalized, raw)

    db.add(job)
    db.flush()
    return job, True


def _apply_normalized(job: Job, norm: JobNormalized, raw: RawJob | None = None) -> None:
    job.title = norm.title or job.title
    job.company = norm.company or job.company
    job.location = norm.location or job.location
    job.country = norm.country or job.country
    # La fuente sabe mejor que el texto si la vacante es remota.
    if raw and raw.remote_type != "unknown":
        job.remote_type = raw.remote_type
    elif norm.remote_type != "unknown":
        job.remote_type = norm.remote_type
    job.seniority = norm.seniority or job.seniority
    job.employment_type = norm.employment_type or job.employment_type
    if norm.salary_min or norm.salary_max:
        job.salary_min = norm.salary_min or None
        job.salary_max = norm.salary_max or None
        job.salary_currency = norm.salary_currency or None
        job.salary_period = norm.salary_period or None
    job.requirements = norm.requirements.model_dump()
    job.tags = list(dict.fromkeys([*(job.tags or []), *norm.tags]))[:25]
    job.embedding = embed(embedding_text(job))


def reanalyze(db: Session, job: Job) -> Job:
    """Fuerza un nuevo análisis con IA de una vacante ya guardada."""
    norm = analyze_job_text(job.description_raw, job.title, job.company)
    _apply_normalized(job, norm)
    db.flush()
    return job


def ingest_source(
    db: Session,
    source_name: str,
    query: str = "",
    limit: int = 30,
    analyze: bool = False,
    country: str = "",
) -> dict:
    """Descarga vacantes de una fuente y las guarda.

    `analyze=False` por defecto: normalizar 30 ofertas con el LLM cuesta dinero y
    tiempo. La heurística basta para poblar el listado; el análisis fino se hace
    cuando abres una vacante concreta.

    Con `country`, se descartan las vacantes a las que no se puede postular desde
    ese país (p. ej. "USA only" para alguien en Colombia). Las fuentes que ya
    filtran en su API no se vuelven a filtrar.
    """
    fetch = fetch_eligible(source_name, query, limit, country)
    return {**fetch.summary(), **store(db, fetch.jobs, analyze)}


@dataclass
class FetchResult:
    source: str
    query: str
    jobs: list[RawJob] = field(default_factory=list)
    fetched: int = 0
    skipped: int = 0
    error: str = ""

    def summary(self) -> dict:
        out = {"source": self.source, "query": self.query, "fetched": self.fetched,
               "skipped": self.skipped}
        if self.error:
            out["error"] = self.error
        return out


def fetch_eligible(source_name: str, query: str, limit: int, country: str = "") -> FetchResult:
    """Solo red, sin base de datos: se puede llamar desde varios hilos a la vez."""
    source = REGISTRY.get(source_name)
    if source is None:
        raise ValueError(f"Fuente desconocida: {source_name}. Disponibles: {list(REGISTRY)}")

    raws = source.fetch(query=query, limit=limit, country=country)
    result = FetchResult(source=source_name, query=query, fetched=len(raws))
    if country and not source.filters_country:
        eligible = [r for r in raws if geo.location_matches(r.location, country)]
        result.skipped = len(raws) - len(eligible)
        raws = eligible
    result.jobs = [r for r in raws if r.title][:limit]
    return result


def store(db: Session, raws: list[RawJob], analyze: bool = False) -> dict:
    created = updated = 0
    for raw in raws:
        _, is_new = upsert_job(db, raw, analyze=analyze)
        created += is_new
        updated += not is_new
    db.commit()
    return {"created": created, "updated": updated}


def ingest_many(
    db: Session,
    sources: list[str],
    queries: list[str],
    limit: int,
    country: str = "",
    analyze: bool = False,
) -> list[dict]:
    """Cada consulta contra cada fuente. Descarga en paralelo, guarda en serie.

    Una fuente caída no tumba el resto: su fila del resultado lleva `error`.
    """
    queries = queries or [""]
    tasks = [(s, q) for s in sources for q in queries]

    def _run(task: tuple[str, str]) -> FetchResult:
        source_name, query = task
        try:
            return fetch_eligible(source_name, query, limit, country)
        except httpx.HTTPError as exc:
            return FetchResult(source_name, query, error=f"fallo de red: {exc}")
        except Exception as exc:  # noqa: BLE001 — cualquier fallo de una fuente se reporta
            return FetchResult(source_name, query, error=str(exc))

    with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as pool:
        fetched = list(pool.map(_run, tasks))

    results = []
    for item in fetched:
        row = item.summary()
        if not item.error:
            row.update(store(db, item.jobs, analyze))
        results.append(row)
    return results
