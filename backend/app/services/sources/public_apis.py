"""Fuentes públicas de vacantes remotas (sin API key)."""

from __future__ import annotations

from datetime import datetime, timezone

from dateutil import parser as date_parser

from app.core.logging import get_logger
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


class RemotiveSource(JobSource):
    """https://remotive.com/api/remote-jobs — feed público, JSON, sin auth."""

    name = "remotive"
    ENDPOINT = "https://remotive.com/api/remote-jobs"

    def fetch(self, query: str = "", limit: int = 50) -> list[RawJob]:
        params: dict = {"limit": min(limit, 100)}
        if query:
            params["search"] = query
        data = self._get(self.ENDPOINT, params=params).json()

        jobs = []
        for item in data.get("jobs", [])[:limit]:
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
    ENDPOINT = "https://remoteok.com/api"

    def fetch(self, query: str = "", limit: int = 50) -> list[RawJob]:
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
            if len(jobs) >= limit:
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
    ENDPOINT = "https://www.arbeitnow.com/api/job-board-api"

    def fetch(self, query: str = "", limit: int = 50) -> list[RawJob]:
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
    RemotiveSource.name: RemotiveSource(),
    RemoteOkSource.name: RemoteOkSource(),
    ArbeitnowSource.name: ArbeitnowSource(),
}


def available_sources() -> list[str]:
    return list(REGISTRY)
