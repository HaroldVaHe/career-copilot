"""La taxonomía es la base del matching determinista: si falla aquí, el score miente."""

from __future__ import annotations

import pytest

from app.services.taxonomy import (
    canonicalize,
    detect_seniority,
    extract_skills,
    normalize_skills,
    seniority_distance,
    years_to_seniority,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("js", "JavaScript"),
        ("JavaScript", "JavaScript"),
        ("postgres", "PostgreSQL"),
        ("k8s", "Kubernetes"),
        ("node.js", "Node.js"),
        ("c#", "C#"),
        ("c++", "C++"),
        ("golang", "Go"),
        ("github actions", "CI/CD"),
    ],
)
def test_canonicalize_aliases(raw, expected):
    assert canonicalize(raw) == expected


def test_canonicalize_tolerates_typos():
    assert canonicalize("Kubernets") == "Kubernetes"
    assert canonicalize("PostgreSQL ") == "PostgreSQL"


def test_canonicalize_keeps_unknown_terms():
    assert canonicalize("Blorptech") == "Blorptech"
    assert canonicalize("") == ""


def test_extract_skills_counts_mentions():
    text = "Usamos Python y python3 con FastAPI. Python es el lenguaje principal."
    counts = extract_skills(text)
    assert counts["Python"] == 3
    assert counts["FastAPI"] == 1


def test_longer_alias_wins_over_shorter():
    """'React Native' no puede contar como una mención de 'React'."""
    counts = extract_skills("Desarrollo apps con React Native desde 2020.")
    assert counts.get("React Native") == 1
    assert "React" not in counts


def test_symbols_do_not_break_word_boundaries():
    counts = extract_skills("Stack: C#, C++ y C. También ASP.NET.")
    assert counts.get("C#") == 1
    assert counts.get("C++") == 1
    assert counts.get(".NET") == 1


def test_extract_skills_ignores_substrings():
    """'Rust' no debe salir de 'frustrante'; 'Go' no debe salir de 'Google'."""
    counts = extract_skills("Fue frustrante configurar Googlebot.")
    assert "Rust" not in counts
    assert "Go" not in counts


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Senior Backend Engineer", "senior"),
        ("Junior Developer", "junior"),
        ("Tech Lead", "lead"),
        ("Engineering Manager", "manager"),
        ("Becario de desarrollo", "intern"),
        ("Desarrollador", ""),
    ],
)
def test_detect_seniority(title, expected):
    assert detect_seniority(title) == expected


def test_seniority_distance():
    assert seniority_distance("senior", "senior") == 0
    assert seniority_distance("mid", "senior") == 1
    assert seniority_distance("junior", "lead") == 3
    assert seniority_distance("senior", "desconocido") == -1


def test_years_to_seniority():
    assert years_to_seniority(0.5) == "junior"
    assert years_to_seniority(2) == "mid"
    assert years_to_seniority(5) == "senior"
    assert years_to_seniority(10) == "lead"


def test_normalize_skills_dedupes():
    assert normalize_skills(["js", "JavaScript", "JS", "python"]) == ["JavaScript", "Python"]
