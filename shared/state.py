"""
state.py — Estado compartido del grafo LangGraph.

Reemplaza a shared/state.py (SharedState + RLock + resolución de conflictos por
prioridad) del proyecto original. En LangGraph la concurrencia se maneja por
diseño del grafo (qué nodos pueden escribir qué campos), no con locks manuales.
Ver documento de diseño §3.5.
"""

from typing import TypedDict
from .schemas import CandidateProfile


class RecruitmentState(TypedDict, total=False):
    # Entrada
    candidate: CandidateProfile
    job_requirements: dict

    # Plan generado por el Orquestador (Deep Agent)
    plan: list[str]

    # Salida de Validación
    is_valid: bool
    validation_issues: list[str]
    sunedu_summary: str

    # Salida de Evaluación
    score: float
    strengths: list[str]
    gaps: list[str]
    breakdown: dict[str, float]
    rag_context_used: str  # políticas de RRHH recuperadas (§3.3, trazabilidad RAG)

    # Salida de Clasificación
    classification: str          # A+ / A / B / C / D
    decision: str                # APPROVED / REJECTED
    rationale: str

    # Salida del swarm final
    email_subject: str
    email_body: str
    closing_report: dict

    # Métricas / auditoría
    tokens_used: int
    errors: list[str]
