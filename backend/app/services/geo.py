"""Países, regiones y elegibilidad por ubicación.

Las bolsas remotas describen dónde se puede trabajar de formas muy distintas:
"Worldwide", "LATAM", "USA only", una lista de 70 países... Este módulo reduce
todo eso a una pregunta: ¿una persona que vive en X puede postular?

Es deliberadamente una tabla pequeña y explícita, no una librería de geodatos:
cubre los países que de verdad aparecen en esas bolsas. Lo que no reconoce se
trata como "no sé", y en caso de duda la vacante se conserva.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

LATAM = "LATAM"
NORTH_AMERICA = "North America"
EUROPE = "Europe"
APAC = "APAC"
MEA = "EMEA"


@dataclass(frozen=True)
class Country:
    name: str  # nombre canónico en inglés (lo que entienden Himalayas y compañía)
    region: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    jobicy: str = ""  # geoSlug de Jobicy si tiene uno propio


_COUNTRIES: list[Country] = [
    # --- Latinoamérica ---
    Country("Argentina", LATAM, ("buenos aires", "cordoba", "rosario"), "argentina"),
    Country("Bolivia", LATAM, ("la paz", "santa cruz de la sierra")),
    Country("Brazil", LATAM, ("brasil", "sao paulo", "rio de janeiro"), "brazil"),
    Country("Chile", LATAM, ("santiago de chile",)),
    Country("Colombia", LATAM, (
        "bogota", "medellin", "cali", "barranquilla", "cartagena", "bucaramanga",
        "cundinamarca", "antioquia", "valle del cauca", "chia", "zipaquira", "pereira",
        "manizales",
    )),
    Country("Costa Rica", LATAM, ("san jose de costa rica",), "costa-rica"),
    Country("Dominican Republic", LATAM, ("republica dominicana", "santo domingo")),
    Country("Ecuador", LATAM, ("quito", "guayaquil")),
    Country("El Salvador", LATAM, ("san salvador",)),
    Country("Guatemala", LATAM, ()),
    Country("Honduras", LATAM, ("tegucigalpa",)),
    Country("Mexico", LATAM, ("cdmx", "ciudad de mexico", "guadalajara", "monterrey"), "mexico"),
    Country("Nicaragua", LATAM, ("managua",)),
    Country("Panama", LATAM, ()),
    Country("Paraguay", LATAM, ("asuncion",)),
    Country("Peru", LATAM, ("lima",)),
    Country("Puerto Rico", LATAM, ("san juan",)),
    Country("Uruguay", LATAM, ("montevideo",)),
    Country("Venezuela", LATAM, ("caracas",)),
    # --- Norteamérica ---
    Country("United States", NORTH_AMERICA, (
        "usa", "us", "u.s.", "united states of america", "estados unidos", "eeuu", "ee.uu.",
    ), "usa"),
    Country("Canada", NORTH_AMERICA, ("toronto", "vancouver", "montreal"), "canada"),
    # --- Europa ---
    Country("Spain", EUROPE, ("espana", "madrid", "barcelona", "valencia", "sevilla"), "spain"),
    Country("Portugal", EUROPE, ("lisboa", "lisbon", "porto"), "portugal"),
    Country("France", EUROPE, ("francia", "paris"), "france"),
    Country("Germany", EUROPE, ("alemania", "deutschland", "berlin", "munich", "hamburg"),
            "germany"),
    Country("Italy", EUROPE, ("italia", "milan", "roma", "rome"), "italy"),
    Country("United Kingdom", EUROPE, ("uk", "u.k.", "reino unido", "england", "london",
                                       "great britain"), "uk"),
    Country("Ireland", EUROPE, ("irlanda", "dublin"), "ireland"),
    Country("Netherlands", EUROPE, ("paises bajos", "holanda", "amsterdam"), "netherlands"),
    Country("Belgium", EUROPE, ("belgica", "brussels"), "belgium"),
    Country("Switzerland", EUROPE, ("suiza", "zurich"), "switzerland"),
    Country("Austria", EUROPE, ("vienna", "viena"), "austria"),
    Country("Poland", EUROPE, ("polonia", "warsaw"), "poland"),
    Country("Sweden", EUROPE, ("suecia", "stockholm"), "sweden"),
    Country("Norway", EUROPE, ("noruega", "oslo"), "norway"),
    Country("Denmark", EUROPE, ("dinamarca", "copenhagen"), "denmark"),
    Country("Finland", EUROPE, ("finlandia", "helsinki"), "finland"),
    Country("Romania", EUROPE, ("rumania", "bucharest"), "romania"),
    Country("Czechia", EUROPE, ("czech republic", "republica checa", "prague"), "czechia"),
    Country("Greece", EUROPE, ("grecia", "athens"), "greece"),
    # --- Asia-Pacífico ---
    Country("India", APAC, ("bangalore", "bengaluru", "mumbai", "delhi", "hyderabad")),
    Country("Philippines", APAC, ("filipinas", "manila"), "philippines"),
    Country("Australia", APAC, ("sydney", "melbourne"), "australia"),
    Country("New Zealand", APAC, ("nueva zelanda", "auckland"), "new-zealand"),
    Country("Japan", APAC, ("japon", "tokyo"), "japan"),
    Country("Singapore", APAC, ("singapur",), "singapore"),
    Country("Indonesia", APAC, ("jakarta",)),
    Country("Vietnam", APAC, ("ho chi minh", "hanoi"), "vietnam"),
    Country("Thailand", APAC, ("tailandia", "bangkok"), "thailand"),
    Country("Malaysia", APAC, ("malasia", "kuala lumpur"), "malaysia"),
    Country("South Korea", APAC, ("corea del sur", "seoul"), "south-korea"),
    Country("China", APAC, ("beijing", "shanghai"), "china"),
    # --- Europa del Este, Oriente Medio y África ---
    Country("South Africa", MEA, ("sudafrica", "cape town", "johannesburg"), "south-africa"),
    Country("Israel", MEA, ("tel aviv",), "israel"),
    Country("United Arab Emirates", MEA, ("uae", "emiratos arabes unidos", "dubai"), "uae"),
    Country("Egypt", MEA, ("egipto", "cairo")),
    Country("Nigeria", MEA, ("lagos",)),
    Country("Kenya", MEA, ("nairobi",)),
    Country("Morocco", MEA, ("marruecos",)),
    Country("Turkey", MEA, ("turquia", "turkiye", "istanbul"), "turkey"),
    Country("Ukraine", EUROPE, ("ucrania", "kyiv", "kiev"), "ukraine"),
]

BY_NAME = {c.name.lower(): c for c in _COUNTRIES}

_REGION_TERMS: dict[str, tuple[str, ...]] = {
    LATAM: ("latam", "latin america", "latinoamerica", "south america", "central america",
            "americas"),
    NORTH_AMERICA: ("north america", "northern america", "americas"),
    EUROPE: ("europe", "european union", "eu", "emea", "cet", "cest"),
    APAC: ("apac", "asia", "asia pacific", "oceania"),
    MEA: ("emea", "middle east", "africa", "mena"),
}

_JOBICY_REGION = {LATAM: "latam", EUROPE: "europe", APAC: "apac", MEA: "emea",
                  NORTH_AMERICA: "usa"}

_GLOBAL_TERMS = ("worldwide", "anywhere", "global", "remote worldwide", "work from anywhere",
                 "any location", "cualquier lugar", "todo el mundo")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return text.lower().strip()


def _has_term(haystack: str, term: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", haystack) is not None


def detect_country(text: str) -> str:
    """Nombre canónico del país que menciona un texto libre ("Chía, Cundinamarca" -> Colombia)."""
    haystack = _norm(text)
    if not haystack:
        return ""
    for country in _COUNTRIES:
        if _has_term(haystack, country.name.lower()):
            return country.name
    for country in _COUNTRIES:
        if any(_has_term(haystack, alias) for alias in country.aliases):
            return country.name
    return ""


def canonical(country: str) -> str:
    """Normaliza lo que escribe el usuario ("México", "usa") al nombre canónico."""
    return detect_country(country) or (country or "").strip()


def region_of(country: str) -> str:
    c = BY_NAME.get((country or "").lower())
    return c.region if c else ""


def jobicy_geo(country: str) -> str:
    """Slug de Jobicy: el del país si existe, si no el de su región."""
    c = BY_NAME.get((country or "").lower())
    if c is None:
        return ""
    return c.jobicy or _JOBICY_REGION.get(c.region, "")


def location_matches(location: str | None, country: str) -> bool:
    """¿Alguien que vive en `country` puede postular a una vacante en `location`?

    Ante la duda devuelve True: una vacante sin ubicación o con un "Remote" a secas
    se conserva, y el usuario decide al abrirla.
    """
    if not country:
        return True
    loc = _norm(location or "")
    if not loc or loc in ("remote", "remoto", "remote job", "fully remote"):
        return True
    if any(_has_term(loc, term) for term in _GLOBAL_TERMS):
        return True
    c = BY_NAME.get(country.lower())
    if c is None:
        return _has_term(loc, _norm(country))
    if _has_term(loc, c.name.lower()) or any(_has_term(loc, a) for a in c.aliases):
        return True
    return any(_has_term(loc, term) for term in _REGION_TERMS.get(c.region, ()))


def sql_patterns(country: str) -> list[str]:
    """Patrones ILIKE equivalentes a `location_matches`, para filtrar en la base."""
    c = BY_NAME.get((canonical(country) or "").lower())
    terms = list(_GLOBAL_TERMS)
    if c is None:
        terms.append(country.strip())
    else:
        terms += [c.name, *c.aliases, *_REGION_TERMS.get(c.region, ())]
    # Los alias de dos letras ("us", "uk", "eu") darían falsos positivos con ILIKE.
    return [f"%{t}%" for t in dict.fromkeys(terms) if len(t) > 2]


def summarize_locations(countries: list[str], focus: str = "") -> str:
    """Resume una lista larga de países elegibles en algo legible y filtrable.

    `["Albania", ..., "Vietnam"]` (70 países) -> "Colombia + 69 países · LATAM, Europe, APAC".
    """
    names = [c for c in countries if c]
    if not names:
        return "Worldwide"
    if len(names) <= 6:
        return ", ".join(names)
    regions = sorted({region_of(n) for n in names} - {""})
    head = focus if focus and focus in names else names[0]
    text = f"{head} + {len(names) - 1} países"
    if regions:
        text += " · " + ", ".join(regions)
    return text[:320]
