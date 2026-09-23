"""Perfiles: cada persona que usa la app con sus propios CV y pipeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProfileRead(BaseModel):
    id: int
    full_name: str
    is_default: bool = False
    headline: str = Field(default="", description="Titular del CV principal del perfil")
    resumes: int = 0
    applications: int = 0
    best_score: float | None = None
    created_at: datetime | None = None


class ProfileWrite(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
