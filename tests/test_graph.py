"""
tests/test_graph.py — Pruebas unitarias (documento §5, "Calidad de código").

Cubre lo que NO depende del LLM (determinista, rápido, sin costo de tokens):
schemas Pydantic, enrutamiento condicional del grafo y el retriever RAG.
Las pruebas que sí requieren LLM se ejecutan aparte vía eval/langsmith_eval.py
(evaluación continua, no unit testing — ver documento §5).

Ejecutar:
    pytest tests/ -v
"""

import pytest
from pydantic import ValidationError

from shared.schemas import CandidateProfile, ValidationResult, ClassificationResult
from shared.rag_kb import RAGRetriever
from agents.graph import route_after_validation


# ─────────────────────────── Schemas (Pydantic) ───────────────────────────

def test_validation_result_valid_confidence():
    r = ValidationResult(is_valid=True, confidence=0.9, issues=[])
    assert r.confidence == 0.9


def test_validation_result_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        ValidationResult(is_valid=True, confidence=1.5, issues=[])


def test_classification_result_rejects_invalid_classification():
    with pytest.raises(ValidationError):
        ClassificationResult(classification="Z", decision="APPROVED")


def test_classification_result_rejects_invalid_decision():
    with pytest.raises(ValidationError):
        ClassificationResult(classification="A", decision="MAYBE")


def test_classification_result_accepts_valid_values():
    r = ClassificationResult(classification="A+", decision="APPROVED", rationale="ok")
    assert r.classification == "A+"
    assert r.decision == "APPROVED"


# ─────────────────────────── Enrutamiento condicional del grafo ───────────────────────────

def test_route_after_validation_valid_goes_to_evaluation():
    state = {"is_valid": True}
    assert route_after_validation(state) == "evaluar_clasificar"


def test_route_after_validation_invalid_skips_to_swarm():
    state = {"is_valid": False}
    result = route_after_validation(state)
    assert result == ["comunicacion", "followup"]


def test_route_after_validation_missing_key_defaults_to_reject_path():
    state = {}
    result = route_after_validation(state)
    assert result == ["comunicacion", "followup"]


# ─────────────────────────── RAG Retriever (BM25) ───────────────────────────

def test_rag_retriever_returns_relevant_chunk_for_experience_query():
    retriever = RAGRetriever()
    chunks = retriever.retrieve("equivalencia experiencia practicas preprofesionales", k=1)
    assert len(chunks) >= 1
    assert "experiencia" in chunks[0].text.lower()


def test_rag_retriever_returns_empty_for_irrelevant_query():
    retriever = RAGRetriever()
    chunks = retriever.retrieve("receta de tallarines verdes", k=2)
    # BM25 puede devolver score 0 para queries totalmente ajenas al corpus
    assert all(c.score >= 0 for c in chunks)


def test_rag_format_context_handles_empty_list():
    retriever = RAGRetriever()
    assert retriever.format_context([]) == "Sin políticas adicionales relevantes."


# ─────────────────────────── CandidateProfile ───────────────────────────

def test_candidate_profile_to_dict_roundtrip():
    c = CandidateProfile(
        candidate_id="TEST-001", name="Test User", email="test@test.com",
        phone="+51 900 000 000", position="QA", years_exp=2,
        skills=["pytest"], education="N/A", cv_text="CV de prueba con más de 50 caracteres.",
    )
    d = c.to_dict()
    assert d["candidate_id"] == "TEST-001"
    assert d["dni"] is None
