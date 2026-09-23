"""Fuentes públicas de vacantes (sin API key).

Himalayas y Jobicy son las globales: filtran por país o región en la propia API,
así que son las que mejor responden a "busca para alguien que vive en Colombia".
Remotive y RemoteOK son remotas sin filtro de país (se filtra al ingerir).
Arbeitnow es casi entera de Alemania: sigue disponible, pero no entra por defecto.
"""

from __future__ import annotations

from datetime import datetime, timezone

from dateutil import parser as date_parser

from app.core.logging import get_logger
from app.services import geo
from app.services.documents import html_to_text
from app.services.sources.base import JobSource, RawJob

log = get_logger(__name__)


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        parsed = date_parser.parse(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError, date_parser.ParserError):
        return None


def _salary_text(low, high, currency: str | None, period: str = "year") -> str:
    if not low and not high:
        return ""
    low, high = low or high, high or low
    return f"{currency or ''} {int(low):,} - {int(high):,} / {period}".strip()


class HimalayasSource(JobSource):
    """https://himalayas.app/jobs/api — remoto global, filtra por país de residencia."""

    name = "himalayas"
    label = "Himalayas"
    description = "Remoto global. Filtra por el país donde vives."
    filters_country = True
    ENDPOINT = "https://himalayas.app/jobs/api/search"
    PAGE_SIZE = 20  # fijo en la API

    def fetch(self, query: str = "", limit: int = 50, country: str = "") -> list[RawJob]:
        jobs: list[RawJob] = []
        page = 1
        while len(jobs) < limit and page <= 5:
            params: dict = {"page": page}
            if query:
                params["q"] = query
            if country:
                params["country"] = country
            items = self._get(self.ENDPOINT, params=params).json().get("jobs", [])
            if not items:
                break
            for item in items:
                jobs.append(
                    RawJob(
                        source=self.name,
                        external_id=str(item.get("guid") or item.get("applicationLink") or ""),
                        title=item.get("title", ""),
                        company=item.get("companyName", ""),
                        url=item.get("applicationLink") or item.get("guid") or "",
                        location=geo.summarize_locations(
                            item.get("locationRestrictions") or [], country
                        ),
                        description_raw=html_to_text(item.get("description", "")),
                        remote_type="remote",
                        employment_type=item.get("employmentType", "") or "",
                        salary_text=_salary_text(
                            item.get("minSalary"), item.get("maxSalary"), item.get("currency")
                        ),
                        tags=[*(item.get("parentCategories") or []),
                              *(item.get("seniority") or [])][:10],
                        posted_at=_parse_date(item.get("pubDate")),
                    )
                )
                if len(jobs) >= limit:
                    break
            if len(items) < self.PAGE_SIZE:
                break
            page += 1
        return jobs


class JobicySource(JobSource):
    """https://jobicy.com/api/v2/remote-jobs — remoto, filtra por país o región (LATAM, Europe...)."""

    name = "jobicy"
    label = "Jobicy"
    description = "Remoto. Filtra por país o, si no lo tiene, por región (LATAM, Europa, APAC)."
    filters_country = True
    ENDPOINT = "https://jobicy.com/api/v2/remote-jobs"

    def fetch(self, query: str = "", limit: int = 50, country: str = "") -> list[RawJob]:
        params: dict = {"count": min(max(limit, 1), 100)}
        if query:
            params["tag"] = query
        slug = geo.jobicy_geo(country)
        if slug:
            params["geo"] = slug
        data = self._get(self.ENDPOINT, params=params).json()

        jobs = []
        for item in data.get("jobs", [])[:limit]:
            jobs.append(
                RawJob(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=item.get("jobTitle", ""),
                    company=item.get("companyName", ""),
                    url=item.get("url", ""),
                    location=(item.get("jobGeo") or "").replace(",  ", ", "),
                    description_raw=html_to_text(item.get("jobDescription", "")),
                    remote_type="remote",
                    employment_type=", ".join(item.get("jobType") or []),
                    salary_text=_salary_text(
                        item.get("annualSalaryMin"),
                        item.get("annualSalaryMax"),
                        item.get("salaryCurrency"),
                    ),
                    tags=list(item.get("jobIndustry") or [])[:10],
                    posted_at=_parse_date(item.get("pubDate")),
                )
            )
        return jobs


class RemotiveSource(JobSource):
    """https://remotive.com/api/remote-jobs — feed público, JSON, sin auth."""

    name = "remotive"
    label = "Remotive"
    description = "Remoto, sobre todo tecnología. Indica en qué países se acepta cada vacante."
    ENDPOINT = "https://remotive.com/api/remote-jobs"

    def fetch(self, query: str = "", limit: int = 50, country: str = "") -> list[RawJob]:
        params: dict = {"limit": min(limit * 3 if country else limit, 100)}
        if query:
            params["search"] = query
        data = self._get(self.ENDPOINT, params=params).json()
        # El feed público ya no aplica `search`: devuelve siempre las mismas
        # vacantes. Se filtra aquí por título, categoría y etiquetas.
        words = [w for w in query.lower().split() if len(w) > 2]

        jobs = []
        for item in data.get("jobs", []):
            haystack = " ".join(
                [item.get("title", ""), item.get("category", ""), *(item.get("tags") or [])]
            ).lower()
            if words and not all(w in haystack for w in words):
                continue
            jobs.append(
                RawJob(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    url=item.get("url", ""),
                    location=item.get("candidate_required_location", ""),
                    description_raw=html_to_text(item.get("description", "")),
                    remote_type="remote",
                    employment_type=item.get("job_type", ""),
                    salary_text=item.get("salary", "") or "",
                    tags=item.get("tags", []) or [],
                    posted_at=_parse_date(item.get("publication_date")),
                )
            )
        return jobs


class RemoteOkSource(JobSource):
    """https://remoteok.com/api — el primer elemento del array es un aviso legal."""

    name = "remoteok"
    label = "RemoteOK"
    description = "Remoto, tecnología. Sin filtro de país en la API; a veces responde lento."
    ENDPOINT = "https://remoteok.com/api"

    def fetch(self, query: str = "", limit: int = 50, country: str = "") -> list[RawJob]:
        data = self._get(self.ENDPOINT).json()
        needle = query.lower().strip()

        jobs = []
        for item in data:
            if not isinstance(item, dict) or "id" not in item:
                continue  # el disclaimer inicial
            haystack = " ".join(
                str(item.get(k, "")) for k in ("position", "company", "description", "tags")
            ).lower()
            if needle and needle not in haystack:
                continue
            jobs.append(
                RawJob(
                    source=self.name,
                    external_id=str(item.get("id")),
                    title=item.get("position", "") or item.get("title", ""),
                    company=item.get("company", ""),
                    url=item.get("url", "") or item.get("apply_url", ""),
                    location=item.get("location", "") or "Remote",
                    description_raw=html_to_text(item.get("description", "")),
                    remote_type="remote",
                    salary_text=_remoteok_salary(item),
                    tags=item.get("tags", []) or [],
                    posted_at=_parse_date(item.get("date") or item.get("epoch")),
                )
            )
            if len(jobs) >= limit * (3 if country else 1):
                break
        return jobs


def _remoteok_salary(item: dict) -> str:
    low, high = item.get("salary_min"), item.get("salary_max")
    if low and high:
        return f"${low:,} - ${high:,} USD/year"
    return ""


class ArbeitnowSource(JobSource):
    """https://www.arbeitnow.com/api/job-board-api — bolsa europea, JSON público."""

    name = "arbeitnow"
    label = "Arbeitnow"
    description = "Europa, casi todo Alemania. Desactivada por defecto."
    default_enabled = False
    ENDPOINT = "https://www.arbeitnow.com/api/job-board-api"

    def fetch(self, query: str = "", limit: int = 50, country: str = "") -> list[RawJob]:
        needle = query.lower().strip()
        jobs: list[RawJob] = []
        page = 1

        while len(jobs) < limit and page <= 5:
            payload = self._get(self.ENDPOINT, params={"page": page}).json()
            items = payload.get("data", [])
            if not items:
                break

            for item in items:
                haystack = " ".join(
                    str(item.get(k, "")) for k in ("title", "company_name", "description")
                ).lower()
                if needle and needle not in haystack:
                    continue
                jobs.append(
                    RawJob(
                        source=self.name,
                        external_id=str(item.get("slug", "")),
                        title=item.get("title", ""),
                        company=item.get("company_name", ""),
                        url=item.get("url", ""),
                        location=item.get("location", ""),
                        description_raw=html_to_text(item.get("description", "")),
                        remote_type="remote" if item.get("remote") else "onsite",
                        tags=item.get("tags", []) or [],
                        posted_at=_parse_date(item.get("created_at")),
                    )
                )
                if len(jobs) >= limit:
                    break
            page += 1
        return jobs


REGISTRY: dict[str, JobSource] = {
    source.name: source
    for source in (
        HimalayasSource(),
        JobicySource(),
        RemotiveSource(),
        RemoteOkSource(),
        ArbeitnowSource(),
    )
}


def available_sources() -> list[str]:
    return list(REGISTRY)


def default_sources() -> list[str]:
    return [name for name, source in REGISTRY.items() if source.default_enabled]
