"""
graph.py — Construye el Deep Agent sobre LangGraph (documento §3.5 y §3.6).

Reemplaza a agents/orchestrator.py (ThreadPoolExecutor manual + SharedState con RLock)
del proyecto original por:
- Un StateGraph con nodos = subagentes (responsabilidad única, igual que antes).
- Aristas condicionales para el rechazo temprano en Validación.
- Un tramo paralelo real (fan-out) para Comunicación + FollowUp (el "swarm").
- Checkpointing en SQLite (persistencia y reanudación, RF-08).
- Un punto de interrupción (HITL) en Clasificación para casos frontera.
"""

import os
from datetime import datetime

from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.errors import NodeInterrupt

from shared.state import RecruitmentState
from shared.schemas import (
    ValidationResult, EvaluationResult, ClassificationResult,
    CommunicationResult,
)
from tools.pipeline_tools import verify_sunedu_credentials, send_recruitment_email, save_pipeline_report
from tools.rag_tools import retrieve_hr_policies
from .prompts import (
    VALIDATION_PROMPT, EVALUATION_PROMPT, CLASSIFICATION_PROMPT,
    COMMUNICATION_PROMPT,
)

# Modelo por defecto: llama-3.3-70b-versatile (el mismo del proyecto original).
# Fallback a llama-3.1-8b-instant si el modelo grande no responde (§3.8 Robustez).
MODEL_PRIMARY = "llama-3.3-70b-versatile"
MODEL_FALLBACK = "llama-3.1-8b-instant"


def _llm(model: str = MODEL_PRIMARY, temperature: float = 0.2) -> ChatGroq:
    return ChatGroq(model=model, temperature=temperature, max_retries=3)


def _call_structured(prompt: str, user_content: str, schema):
    """Llama al LLM con salida estructurada obligatoria (Pydantic), con fallback de modelo."""
    try:
        llm = _llm(MODEL_PRIMARY).with_structured_output(schema)
        return llm.invoke([("system", prompt), ("human", user_content)])
    except Exception as e:
        print(f"  [WARN] Falla con {MODEL_PRIMARY} ({e}); degradando a {MODEL_FALLBACK}")
        llm = _llm(MODEL_FALLBACK).with_structured_output(schema)
        return llm.invoke([("system", prompt), ("human", user_content)])


# ─────────────────────────── Nodos ───────────────────────────

def orquestador_planifica(state: RecruitmentState) -> dict:
    """Deep Agent: decide el orden de subagentes. Hoy determinista con un único
    punto de decisión dinámica (saltar evaluación si el CV ya luce inválido)."""
    plan = ["validar", "evaluar_clasificar", "swarm(comunicacion, followup)"]
    return {"plan": plan}


def validar(state: RecruitmentState) -> dict:
    candidate = state["candidate"]
    sunedu_summary = ""
    if candidate.dni:
        sunedu = verify_sunedu_credentials(candidate.dni, candidate.education)
        sunedu_summary = sunedu["summary"]

    user_content = (
        f"Candidato: {candidate.to_dict()}\n"
        f"Resultado SUNEDU: {sunedu_summary or 'No se proporcionó DNI'}"
    )
    result: ValidationResult = _call_structured(VALIDATION_PROMPT, user_content, ValidationResult)
    return {
        "is_valid": result.is_valid,
        "validation_issues": result.issues,
        "sunedu_summary": sunedu_summary,
    }


def evaluar_clasificar(state: RecruitmentState) -> dict:
    candidate = state["candidate"]
    job = state["job_requirements"]

    # RAG (§3.3): recupera políticas de RRHH relevantes al puesto + skills del
    # candidato antes de puntuar, en vez de confiar solo en el prompt estático.
    rag_query = f"{job.get('position', '')} {' '.join(candidate.skills)} {candidate.years_exp} años"
    hr_policies_context = retrieve_hr_policies(rag_query, k=2)

    eval_input = (
        f"Candidato: {candidate.to_dict()}\n"
        f"Requisitos del puesto: {job}\n"
        f"Políticas de RRHH relevantes (RAG):\n{hr_policies_context}"
    )
    ev: EvaluationResult = _call_structured(EVALUATION_PROMPT, eval_input, EvaluationResult)

    class_input = f"Score: {ev.score}\nFortalezas: {ev.strengths}\nBrechas: {ev.gaps}"
    cl: ClassificationResult = _call_structured(CLASSIFICATION_PROMPT, class_input, ClassificationResult)

    # HITL dinámico: pausa el grafo si cae en la banda frontera B/C (score 50-59)
    # o si SUNEDU no pudo verificar el título — ver documento §3.5 "Human-in-the-loop".
    sunedu_not_verified = "NO COINCIDE" in state.get("sunedu_summary", "") or \
                        "No se encontraron" in state.get("sunedu_summary", "")
    if 50 <= ev.score <= 59 or sunedu_not_verified:
        raise NodeInterrupt(
            f"Revisión humana requerida: score={ev.score} (frontera) o SUNEDU no verificado. "
            f"Aprobar/editar/rechazar antes de continuar."
        )

    return {
        "score": ev.score,
        "strengths": ev.strengths,
        "gaps": ev.gaps,
        "breakdown": ev.breakdown,
        "rag_context_used": hr_policies_context,
        "classification": cl.classification,
        "decision": cl.decision,
        "rationale": cl.rationale,
    }


def comunicacion(state: RecruitmentState) -> dict:
    candidate = state["candidate"]
    decision = state.get("decision", "REJECTED")
    gaps = state.get("gaps", [])
    user_content = f"Candidato: {candidate.name}\nDecisión: {decision}\nBrechas: {gaps}"
    result: CommunicationResult = _call_structured(COMMUNICATION_PROMPT, user_content, CommunicationResult)
    send_recruitment_email(candidate.email, result.subject, result.body)
    return {"email_subject": result.subject, "email_body": result.body}


def followup(state: RecruitmentState) -> dict:
    candidate = state["candidate"]
    report = {
        "candidate_id": candidate.candidate_id,
        "name": candidate.name,
        "score": state.get("score"),
        "classification": state.get("classification"),
        "decision": state.get("decision", "REJECTED_TEMPRANO"),
        "closed_at": datetime.utcnow().isoformat(),
    }
    save_pipeline_report(candidate.candidate_id, report)
    return {"closing_report": report}


# ─────────────────────────── Aristas condicionales ───────────────────────────

def route_after_validation(state: RecruitmentState):
    """Si es válido, sigue a evaluación. Si no, salta directo al swarm final
    (fan-out a comunicación + followup) para el rechazo temprano."""
    if state.get("is_valid"):
        return "evaluar_clasificar"
    return ["comunicacion", "followup"]


# ─────────────────────────── Construcción del grafo ───────────────────────────

def build_graph(checkpoint_db_path: str = None, use_local_checkpointer: bool = True):
    """Construye el grafo.

    use_local_checkpointer=True (default): usa SqliteSaver local — modo para
    `python main.py` / desarrollo / pytest.

    use_local_checkpointer=False: NO adjunta checkpointer propio — usado por
    LangGraph Platform, que inyecta su propio checkpointer administrado
    (Postgres) al desplegar. Ver langgraph.json y documento §8.3.
    """
    graph = StateGraph(RecruitmentState)
    graph.add_node("orquestador_planifica", orquestador_planifica)
    graph.add_node("validar", validar)
    graph.add_node("evaluar_clasificar", evaluar_clasificar)
    graph.add_node("comunicacion", comunicacion)
    graph.add_node("followup", followup)

    graph.add_edge(START, "orquestador_planifica")
    graph.add_edge("orquestador_planifica", "validar")
    graph.add_conditional_edges(
        "validar", route_after_validation,
        ["evaluar_clasificar", "comunicacion", "followup"],
    )
    graph.add_edge("evaluar_clasificar", "comunicacion")
    graph.add_edge("evaluar_clasificar", "followup")
    graph.add_edge("comunicacion", END)
    graph.add_edge("followup", END)

    if not use_local_checkpointer:
        return graph.compile()  # LangGraph Platform inyecta su propio checkpointer

    import sqlite3
    checkpoint_db_path = checkpoint_db_path or os.getenv("CHECKPOINT_DB_PATH", "checkpoints.sqlite")
    conn = sqlite3.connect(checkpoint_db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return graph.compile(checkpointer=checkpointer)


def build_graph_for_platform():
    """Punto de entrada usado por langgraph.json para LangGraph Platform.
    Sin checkpointer propio: la plataforma inyecta el suyo (Postgres administrado)."""
    return build_graph(use_local_checkpointer=False)