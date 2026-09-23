"""Países, regiones y elegibilidad por ubicación de las vacantes remotas."""

from __future__ import annotations

import pytest

from app.services import geo


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Chía, Colombia", "Colombia"),
        ("Chía, Cundinamarca", "Colombia"),  # solo región: se deduce el país
        ("Medellín", "Colombia"),
        ("Ciudad de México, México", "Mexico"),
        ("Madrid, España", "Spain"),
        ("Remote - USA", "United States"),
        ("", ""),
        ("Planeta Tierra", ""),
    ],
)
def test_detect_country(text, expected):
    assert geo.detect_country(text) == expected


def test_short_aliases_do_not_match_inside_words():
    # "us" no debe encontrarse dentro de "Russia" ni "business"
    assert geo.detect_country("Business hub") == ""


@pytest.mark.parametrize(
    ("location", "eligible"),
    [
        ("Worldwide", True),
        ("Anywhere", True),
        ("", True),  # sin ubicación: ante la duda se conserva
        ("Remote", True),
        ("LATAM", True),
        ("Northern America, LATAM, Europe, APAC", True),
        ("USA, Canada, Argentina, Mexico, Peru", False),  # Colombia no está
        ("USA only", False),
        ("Berlin", False),
        ("Colombia + 72 países · APAC, EMEA, Europe, LATAM", True),
    ],
)
def test_location_matches_for_someone_in_colombia(location, eligible):
    assert geo.location_matches(location, "Colombia") is eligible


def test_location_matches_without_country_keeps_everything():
    assert geo.location_matches("USA only", "") is True


def test_jobicy_uses_country_slug_or_falls_back_to_region():
    assert geo.jobicy_geo("Mexico") == "mexico"
    assert geo.jobicy_geo("Colombia") == "latam"  # Jobicy no tiene slug para Colombia
    assert geo.jobicy_geo("Spain") == "spain"
    assert geo.jobicy_geo("Atlantis") == ""


def test_summarize_long_lists_keeps_focus_country_and_regions():
    countries = ["Albania", "Argentina", "Brazil", "Canada", "Colombia", "Germany", "Japan",
                 "Spain", "United States"]
    summary = geo.summarize_locations(countries, focus="Colombia")
    assert summary.startswith("Colombia + 8 países")
    assert "LATAM" in summary
    assert geo.location_matches(summary, "Colombia")


def test_summarize_empty_means_worldwide():
    assert geo.summarize_locations([]) == "Worldwide"


def test_sql_patterns_skip_two_letter_aliases():
    patterns = geo.sql_patterns("United States")
    assert "%United States%" in patterns
    assert "%us%" not in patterns
    assert "%worldwide%" in patterns
