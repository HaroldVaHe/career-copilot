"""Esquema estricto del CV.

Es a la vez el contrato de la API y el `output_format` que se le pasa a Claude
para la extracción estructurada, así que los `description` de cada campo son
instrucciones reales para el modelo: vale la pena cuidarlos.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContactInfo(BaseModel):
    full_name: str = Field(default="", description="Nombre completo del candidato")
    headline: str = Field(default="", description="Titular profesional, ej. 'Backend Engineer'")
    email: str = ""
    phone: str = ""
    location: str = Field(default="", description="Ciudad, País")
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""


class ExperienceItem(BaseModel):
    company: str = ""
    role: str = ""
    location: str = ""
    start_date: str = Field(default="", description="Formato YYYY-MM cuando sea deducible")
    end_date: str = Field(default="", description="YYYY-MM, o 'present' si es el trabajo actual")
    is_current: bool = False
    bullets: list[str] = Field(
        default_factory=list,
        description="Logros y responsabilidades, un bullet por línea, textual del CV",
    )
    technologies: list[str] = Field(
        default_factory=list, description="Tecnologías mencionadas explícitamente en este rol"
    )


class EducationItem(BaseModel):
    institution: str = ""
    degree: str = ""
    field_of_study: str = ""
    start_date: str = ""
    end_date: str = ""
    notes: str = ""


class CertificationItem(BaseModel):
    name: str = ""
    issuer: str = ""
    date: str = ""
    credential_url: str = ""


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    url: str = ""


class LanguageItem(BaseModel):
    language: str = ""
    level: str = Field(default="", description="Ej. nativo, C1, profesional, básico")


class SkillSet(BaseModel):
    languages: list[str] = Field(default_factory=list, description="Lenguajes de programación")
    frameworks: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    cloud_devops: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list)

    def flat(self) -> list[str]:
        """Todas las skills técnicas en una lista (sin soft skills)."""
        return [
            *self.languages,
            *self.frameworks,
            *self.databases,
            *self.cloud_devops,
            *self.tools,
            *self.other,
        ]


class ResumeData(BaseModel):
    """Representación estructurada completa de un CV."""

    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str = Field(default="", description="Perfil o resumen profesional, si existe")
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    skills: SkillSet = Field(default_factory=SkillSet)
    certifications: list[CertificationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    total_years_experience: float = Field(
        default=0.0, description="Años totales de experiencia profesional, estimado de las fechas"
    )
    detected_seniority: str = Field(
        default="",
        description="Uno de: intern, junior, mid, senior, lead, principal, manager",
    )
