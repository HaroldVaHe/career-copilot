"""Auditoría ATS, embeddings y diff: la parte determinista, que debe ser estable."""

from __future__ import annotations

from app.schemas.resume import ExperienceItem, ResumeData, SkillSet
from app.services import ats
from app.services.documents import DocumentSignals, clean_text, html_to_text
from app.services.embeddings import cosine, embed_local
from app.services.tailoring import word_diff


def _resume(bullets: list[str], skills: list[str] | None = None) -> ResumeData:
    return ResumeData(
        summary="Ingeniera backend.",
        experience=[
            ExperienceItem(company="Acme", role="Backend Engineer", bullets=bullets),
        ],
        skills=SkillSet(languages=skills or ["Python", "Go"]),
    )


# --------------------------------------------------------------------------
# Cuantificación
# --------------------------------------------------------------------------
def test_quantified_bullets_score_higher_than_vague_ones():
    strong = _resume(
        [
            "Reduje la latencia p99 un 78% migrando a un pool de conexiones",
            "Automaticé el despliegue, bajando de 45 minutos a 4",
        ]
    )
    weak = _resume(
        [
            "Responsable del mantenimiento de la plataforma",
            "Ayudé al equipo con varias tareas",
        ]
    )

    strong_report = ats.analyze(strong, "texto", use_llm=False)
    weak_report = ats.analyze(weak, "texto", use_llm=False)

    assert (
        strong_report.breakdown.achievement_quantification
        > weak_report.breakdown.achievement_quantification + 30
    )


def test_passive_openers_produce_a_finding():
    report = ats.analyze(
        _resume(["Responsable de la base de datos"]), "texto", use_llm=False
    )
    areas = {f.area for f in report.findings}
    assert "redacción" in areas


def test_empty_resume_flags_critical_findings():
    report = ats.analyze(ResumeData(), "", use_llm=False)
    assert report.overall_score < 40
    assert any(f.severity == "critical" for f in report.findings)
    assert "experiencia" in report.missing_sections


# --------------------------------------------------------------------------
# Legibilidad para el ATS
# --------------------------------------------------------------------------
def test_two_column_layout_is_penalized():
    resume = _resume(["Reduje costes un 20%"])
    single = ats.analyze(
        resume, "texto", DocumentSignals(pages=1, words=400, has_text_layer=True), use_llm=False
    )
    double = ats.analyze(
        resume,
        "texto",
        DocumentSignals(pages=1, words=400, has_text_layer=True, likely_multicolumn=True),
        use_llm=False,
    )
    assert double.breakdown.ats_parseability < single.breakdown.ats_parseability


def test_scanned_pdf_is_a_critical_finding():
    report = ats.analyze(
        _resume(["Reduje costes un 20%"]),
        "texto",
        DocumentSignals(pages=1, words=50, has_text_layer=False),
        use_llm=False,
    )
    critical = [f for f in report.findings if f.severity == "critical"]
    assert any("capa de texto" in f.message for f in critical)


def test_scores_stay_inside_bounds():
    report = ats.analyze(
        _resume(["Reduje la latencia un 78%"] * 10, ["Python"] * 3), "texto", use_llm=False
    )
    values = [
        report.overall_score,
        *report.breakdown.model_dump().values(),
    ]
    assert all(0 <= value <= 100 for value in values)


# --------------------------------------------------------------------------
# Embeddings
# --------------------------------------------------------------------------
def test_local_embedding_is_deterministic():
    assert embed_local("Python y Kubernetes", 256) == embed_local("Python y Kubernetes", 256)


def test_local_embedding_is_normalized():
    vector = embed_local("Python, Django, PostgreSQL", 256)
    assert abs(sum(v * v for v in vector) ** 0.5 - 1.0) < 1e-6


def test_similar_texts_are_closer_than_unrelated_ones():
    backend = embed_local("Backend engineer con Python, Django y PostgreSQL", 512)
    similar = embed_local("Desarrollador backend en Python y Django sobre PostgreSQL", 512)
    unrelated = embed_local("Chef de cocina mediterránea especializado en repostería", 512)

    assert cosine(backend, similar) > cosine(backend, unrelated)


def test_cosine_handles_missing_vectors():
    assert cosine(None, [1.0, 0.0]) == 0.0
    assert cosine([1.0], [1.0, 0.0]) == 0.0
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


# --------------------------------------------------------------------------
# Diff
# --------------------------------------------------------------------------
def test_word_diff_marks_only_what_changed():
    diff = word_diff("Desarrollé una API REST", "Desarrollé una API REST escalable")
    assert [d.kind for d in diff if d.kind != "equal"] == ["insert"]
    assert "escalable" in "".join(d.text for d in diff if d.kind == "insert")


def test_word_diff_on_identical_text_has_no_changes():
    diff = word_diff("mismo texto", "mismo texto")
    assert all(d.kind == "equal" for d in diff)


def test_word_diff_reconstructs_both_sides():
    before, after = "Lideré el equipo de datos", "Lideré el equipo de plataforma"
    diff = word_diff(before, after)
    assert "".join(d.text for d in diff if d.kind in ("equal", "delete")) == before
    assert "".join(d.text for d in diff if d.kind in ("equal", "insert")) == after


# --------------------------------------------------------------------------
# Documentos
# --------------------------------------------------------------------------
def test_html_to_text_keeps_list_structure():
    text = html_to_text("<div><p>Requisitos</p><ul><li>Python</li><li>Docker</li></ul></div>")
    assert "Requisitos" in text
    assert text.count("•") == 2


def test_html_to_text_drops_scripts():
    assert "alert" not in html_to_text("<p>Hola</p><script>alert(1)</script>")


def test_clean_text_collapses_whitespace():
    assert clean_text("Hola   mundo\n\n\n\nadiós") == "Hola mundo\n\nadiós"
