"""
schemas.py — Esquemas de datos del sistema migrado.

- CandidateProfile: sigue siendo un dataclass simple (dato de entrada/almacenamiento).
- ValidationResult / EvaluationResult / ClassificationResult: modelos Pydantic que
  son el CONTRATO obligatorio de salida de cada subagente. Reemplazan al parseo manual
  por regex (_extract_json) del proyecto original — ver documento §3.7.
"""

from dataclasses import dataclass, field
from typing import Optional
from pydantic import BaseModel, Field


@dataclass
class CandidateProfile:
    candidate_id: str
    name: str
    email: str
    phone: str
    position: str
    years_exp: int
    skills: list[str]
    education: str
    cv_text: str
    dni: Optional[str] = None  # requerido para verify_sunedu_credentials
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__


# ───────────────────────── Esquemas de salida (Pydantic) ─────────────────────────

class ValidationResult(BaseModel):
    is_valid: bool
    confidence: float = Field(ge=0, le=1)
    issues: list[str] = Field(default_factory=list)
    recommendation: str = Field(default="")


class EvaluationResult(BaseModel):
    score: float = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Subpuntajes por criterio: experiencia, skills, educacion, calidad_cv",
    )


class ClassificationResult(BaseModel):
    classification: str = Field(pattern=r"^(A\+|A|B|C|D)$")
    decision: str = Field(pattern=r"^(APPROVED|REJECTED)$")
    rationale: str = Field(default="")


class CommunicationResult(BaseModel):
    subject: str
    body: str


class FollowUpResult(BaseModel):
    summary: str
    closed_at_status: str
