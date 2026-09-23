"""Informe PDF del CV y plan de búsqueda heurístico."""

from __future__ import annotations

from app.schemas.ats import AtsFinding, AtsReport, AtsScoreBreakdown, BulletRewrite
from app.schemas.resume import ContactInfo, ExperienceItem, ResumeData, SkillSet
from app.services import job_search
from app.services.report_pdf import _t, build_report_pdf, report_filename


def sample_resume() -> ResumeData:
    return ResumeData(
        contact=ContactInfo(full_name="Ana Pérez Núñez", headline="Diseñadora Gráfica",
                            location="Chía, Cundinamarca", phone="320 000 0000"),
        summary="Diseñadora con 3 años de experiencia.",
        experience=[ExperienceItem(company="AJIN", role="Diseñadora Gráfica",
                                   start_date="2023-07", end_date="present")],
        skills=SkillSet(tools=["Figma", "Photoshop"], soft_skills=["Iniciativa"]),
        total_years_experience=3,
        detected_seniority="junior",
    )


def sample_report() -> AtsReport:
    return AtsReport(
        overall_score=47,
        breakdown=AtsScoreBreakdown(technical_relevance=74, clarity_format=66,
                                    achievement_quantification=7, skill_coverage=7,
                                    ats_parseability=82),
        findings=[
            AtsFinding(severity="info", area="formato", message="Fechas mezcladas", fix="Unifica"),
            AtsFinding(severity="critical", area="métricas", message="Sin cifras → ningún logro",
                       fix="Añade números 🚀"),
        ],
        rewrites=[BulletRewrite(original="Hice piezas", suggestion="Diseñé [N] piezas",
                                invented_facts=True)],
        keyword_density={"Figma": 1, "Photoshop": 3},
        missing_sections=["certificaciones"],
        strengths=["Perfil enfocado"],
        quick_wins=["Añade el portafolio"],
    )


def test_pdf_is_generated_with_every_section():
    pdf = build_report_pdf(sample_resume(), sample_report(), target_role="Graphic Designer")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 3000


def test_pdf_without_audit_still_renders_the_profile():
    pdf = build_report_pdf(sample_resume(), None)
    assert pdf.startswith(b"%PDF")


def test_text_outside_cp1252_is_replaced_not_rendered_as_boxes():
    cleaned = _t("Sin cifras → logro 🚀 <b>")
    assert "-&gt;" in cleaned  # la flecha pasa a "->", escapado para Paragraph
    assert "🚀" not in cleaned
    assert "&lt;b&gt;" in cleaned  # se escapa para Paragraph


def test_report_filename_is_ascii():
    assert report_filename(sample_resume()) == "Informe-CV-Ana-Perez-Nunez.pdf"
    assert report_filename(ResumeData(), label="") == "Informe-CV-CV.pdf"


def test_search_country_falls_back_to_region_then_phone_prefix():
    data = sample_resume()
    assert job_search.detect_resume_country(data) == "Colombia"
    data.contact.location = ""
    data.contact.phone = "+34 600 123 456"
    assert job_search.detect_resume_country(data) == "Spain"


def test_heuristic_queries_split_compound_headlines():
    data = ResumeData(
        contact=ContactInfo(headline="Computer Engineering Student & Automation Technologist"),
        experience=[ExperienceItem(role="IT Assistant")],
    )
    queries = job_search.heuristic_queries(data, target_role=None)
    assert queries == ["Computer Engineering Student", "Automation Technologist", "IT Assistant"]
