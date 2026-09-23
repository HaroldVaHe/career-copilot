"""Contrato común de los agregadores de vacantes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from app.core.logging import get_logger

log = get_logger(__name__)

USER_AGENT = "CareerCopilot/1.0 (+https://github.com/local/career-copilot)"


@dataclass
class RawJob:
    """Vacante tal como llega de la fuente, antes de normalizar con el LLM."""

    source: str
    external_id: str
    title: str = ""
    company: str = ""
    url: str = ""
    location: str = ""
    description_raw: str = ""
    remote_type: str = "unknown"
    employment_type: str = ""
    salary_text: str = ""
    tags: list[str] = field(default_factory=list)
    posted_at: datetime | None = None


class JobSource(ABC):
    """Una fuente de vacantes.

    Todas las implementadas usan APIs públicas y documentadas, sin scraping ni
    API key. Para LinkedIn/Indeed/Glassdoor — que prohíben el scraping en sus
    términos — la vía soportada es la extensión de navegador: capturas la oferta
    que ya estás viendo, en tu sesión, con un clic.

    `country` es el nombre canónico en inglés (ver `services/geo.py`). Las
    fuentes que filtran por país en su API lo usan; las demás lo ignoran y el
    filtro se aplica después, al ingerir.
    """

    name: str = "base"
    label: str = ""
    description: str = ""
    requires_key: bool = False
    # Si entra en la importación cuando el usuario no elige fuentes.
    default_enabled: bool = True
    # True si la API ya filtra por país y no hace falta volver a filtrar.
    filters_country: bool = False

    @abstractmethod
    def fetch(self, query: str = "", limit: int = 50, country: str = "") -> list[RawJob]:
        ...

    def _get(self, url: str, params: dict | None = None, timeout: float = 30.0) -> httpx.Response:
        resp = httpx.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=timeout,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp
