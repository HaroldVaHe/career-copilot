"""Matching CV <-> vacante y normalización heurística de ofertas."""

from __future__ import annotations

from types import SimpleNamespace

from app.schemas.resume import ExperienceItem, ResumeData, SkillSet
from app.services import matching
from app.services.jobs import heuristic_job


def fake_job(hard_skills, seniority="senior", description=""):
    """Sustituto del modelo ORM: matching solo lee atributos, nunca la sesión."""
    return SimpleNamespace(
        id=1,
        title="Backend Engineer",
        company="Acme",
        seniority=seniority,
        description_raw=description,
        embedding=None,
        requirements={"hard_skills": hard_skills, "seniority": seniority},
    )


def fake_resume(skills, seniority="senior", bullets=None):
    data = ResumeData(
        skills=SkillSet(languages=skills),
        detected_seniority=seniority,
        experience=[ExperienceItem(company="X", role="Dev", bullets=bullets or [])],
    )
    return SimpleNamespace(id=1, parsed=data.model_dump(), embedding=None)


# --------------------------------------------------------------------------
def test_full_coverage_when_every_requirement_is_met():
    coverage, matched, missing = matching.skill_breakdown(
        ResumeData(skills=SkillSet(languages=["Python", "Docker"])),
        fake_job([{"name": "Python", "required": True}, {"name": "Docker", "required": True}]),
    )
    assert coverage == 1.0
    assert set(matched) == {"Python", "Docker"}
    assert missing == []


def test_missing_requirement_lowers_coverage():
    coverage, _, missing = matching.skill_breakdown(
        ResumeData(skills=SkillSet(languages=["Python"])),
        fake_job([{"name": "Python", "required": True}, {"name": "Kubernetes", "required": True}]),
    )
    assert coverage == 0.5
    assert missing == ["Kubernetes"]


def test_optional_requirements_weigh_less_than_mandatory_ones():
    """Perder un 'deseable' no puede doler lo mismo que perder un excluyente."""
    resume = ResumeData(skills=SkillSet(languages=["Python"]))

    missing_optional, _, _ = matching.skill_breakdown(
        resume,
        fake_job([{"name": "Python", "required": True}, {"name": "Go", "required": False}]),
    )
    missing_required, _, _ = matching.skill_breakdown(
        resume,
        fake_job([{"name": "Python", "required": True}, {"name": "Go", "required": True}]),
    )
    assert missing_optional > missing_required


def test_aliases_in_the_cv_count_as_matches():
    _, matched, missing = matching.skill_breakdown(
        ResumeData(skills=SkillSet(languages=["JS", "k8s"])),
        fake_job([{"name": "JavaScript", "required": True}, {"name": "Kubernetes", "required": True}]),
    )
    assert set(matched) == {"JavaScript", "Kubernetes"}
    assert missing == []


def test_skills_named_only_inside_experience_still_count():
    """Una tecnología citada en un bullet cuenta, aunque no esté en la lista de skills."""
    resume = ResumeData(
        skills=SkillSet(languages=["Python"]),
        experience=[
            ExperienceItem(
                company="Acme",
                role="Dev",
                bullets=["Desplegué el clúster de Kubernetes que soporta el producto"],
            )
        ],
    )
    _, matched, missing = matching.skill_breakdown(
        resume, fake_job([{"name": "Kubernetes", "required": True}])
    )
    assert matched == ["Kubernetes"]
    assert missing == []


def test_requirements_fall_back_to_the_description_text():
    """Si la oferta no se analizó con IA, se leen las skills del texto crudo."""
    job = fake_job([], description="Buscamos experiencia con Python y Terraform.")
    _, matched, missing = matching.skill_breakdown(
        ResumeData(skills=SkillSet(languages=["Python"])), job
    )
    assert "Python" in matched
    assert "Terraform" in missing


# --------------------------------------------------------------------------
def test_seniority_fit_is_best_on_an_exact_match():
    resume = ResumeData(detected_seniority="senior")
    assert matching.seniority_fit(resume, fake_job([], "senior")) == 1.0
    assert matching.seniority_fit(resume, fake_job([], "mid")) < 1.0
    assert matching.seniority_fit(resume, fake_job([], "intern")) < matching.seniority_fit(
        resume, fake_job([], "mid")
    )


def test_unknown_seniority_is_neutral():
    score = matching.seniority_fit(ResumeData(), fake_job([], ""))
    assert 0.4 < score < 0.8


def test_compute_returns_bounded_scores():
    result = matching.compute(
        fake_resume(["Python", "Docker"]),
        fake_job([{"name": "Python", "required": True}]),
    )
    assert 0 <= result.score <= 100
    assert result.matched_skills == ["Python"]


def test_better_profile_scores_higher():
    job = fake_job(
        [
            {"name": "Python", "required": True},
            {"name": "Kubernetes", "required": True},
            {"name": "PostgreSQL", "required": True},
        ]
    )
    strong = matching.compute(fake_resume(["Python", "Kubernetes", "PostgreSQL"]), job)
    weak = matching.compute(fake_resume(["PHP"], seniority="junior"), job)
    assert strong.score > weak.score + 20


# --------------------------------------------------------------------------
def test_heuristic_job_reads_salary_range_and_currency():
    job = heuristic_job("Ofrecemos 65000 - 85000 EUR anuales.", "Backend Engineer")
    assert job.salary_min == 65000
    assert job.salary_max == 85000
    assert job.salary_currency == "EUR"
    assert job.salary_period == "year"


def test_heuristic_job_reads_currency_before_the_numbers():
    job = heuristic_job("Rango: $90,000 - $120,000 al año.", "Engineer")
    assert job.salary_min == 90000
    assert job.salary_currency == "USD"


def test_heuristic_job_detects_modality():
    assert heuristic_job("Puesto 100% remoto.", "Dev").remote_type == "remote"
    assert heuristic_job("Modelo híbrido, 2 días en oficina.", "Dev").remote_type == "hybrid"
    assert heuristic_job("Trabajo presencial en Madrid.", "Dev").remote_type == "onsite"
    assert heuristic_job("Buscamos un desarrollador.", "Dev").remote_type == "unknown"


def test_heuristic_job_separates_mandatory_from_optional():
    job = heuristic_job(
        "Requisitos imprescindibles: Python, Docker.\nValorable: Go, GraphQL.",
        "Backend Engineer",
    )
    required = {s.name for s in job.requirements.hard_skills if s.required}
    assert "Python" in required
    assert "Docker" in required


def test_heuristic_job_reads_years_of_experience():
    job = heuristic_job("Pedimos 5 años de experiencia en backend.", "Dev")
    assert job.requirements.years_experience == 5
