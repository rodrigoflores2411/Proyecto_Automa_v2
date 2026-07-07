"""
rag_tools.py — Tool de recuperación RAG (documento §3.3 y §3.4).

Expone retrieve_hr_policies como una tool más del catálogo, para que el
EvaluationAgent razone con las políticas de RRHH relevantes al puesto en
vez de depender solo de lo que viene hardcodeado en el prompt (§6).
"""

from shared.rag_kb import RAGRetriever

_retriever = RAGRetriever()


def retrieve_hr_policies(query: str, k: int = 2) -> str:
    """Ficha de herramienta — Recuperación de políticas de RRHH (RAG).

    Entrada: query en texto libre (ej. "equivalencia de experiencia practicas").
    Salida: contexto formateado con las k políticas más relevantes (BM25).
    Uso: EvaluationAgent la invoca antes de puntuar, con la posición y
    principales skills del candidato como query.
    """
    chunks = _retriever.retrieve(query, k=k)
    return _retriever.format_context(chunks)
