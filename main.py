"""
main.py — Punto de entrada del sistema migrado a Deep Agent + LangGraph.

Uso:
    python main.py

Requiere un archivo .env (copiar de .env.example) con GROQ_API_KEY como mínimo.
"""

import os
from dotenv import load_dotenv

load_dotenv()

from shared.schemas import CandidateProfile
from agents.graph import build_graph

JOB_REQUIREMENTS = {
    "position": "Desarrollador Backend Senior",
    "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "min_years_exp": 4,
    "education": "Ingeniería de Sistemas",
    "description": "Backend developer con experiencia en microservicios.",
}

# Mismos casos de prueba que tests/test_cases.py del proyecto original (§5.1 golden set)
CANDIDATES = [
    CandidateProfile(
        candidate_id="C001", name="Ana García", email="ana.garcia@email.com",
        phone="+51 999 111 111", position="Desarrollador Backend Senior", years_exp=6,
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes"],
        education="Ingeniería de Sistemas", dni="12345678",
        cv_text="6 años de experiencia liderando equipos backend con Python y FastAPI. "
                "Experta en PostgreSQL, Docker y Kubernetes en producción.",
    ),
    CandidateProfile(
        candidate_id="C004", name="María Torres", email="sin-arroba-email",
        phone="", position="Desarrollador Backend Senior", years_exp=1,
        skills=[], education="", dni="",
        cv_text="Soy dev.",
    ),
]


def run_candidate(app, candidate: CandidateProfile):
    config = {"configurable": {"thread_id": candidate.candidate_id}}
    initial_state = {"candidate": candidate, "job_requirements": JOB_REQUIREMENTS}

    print(f"\n=== Procesando {candidate.name} ({candidate.candidate_id}) ===")
    for event in app.stream(initial_state, config=config, stream_mode="values"):
        pass  # el estado final queda en 'event' tras la última actualización

    state = app.get_state(config)
    if state.next:
        print(f"  ⏸  PAUSADO para revisión humana (HITL). Nodo pendiente: {state.next}")
        print("     Para continuar tras revisión: app.invoke(None, config=config)")
    else:
        print(f"  ✅ Completado: {state.values.get('classification', 'RECHAZO_TEMPRANO')} "
              f"/ {state.values.get('decision', state.values.get('validation_issues'))}")
    return state


def main():
    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit(
            "Falta GROQ_API_KEY. Copia .env.example a .env y completa tu API key "
            "(gratis en https://console.groq.com/keys)."
        )

    app = build_graph()
    for candidate in CANDIDATES:
        run_candidate(app, candidate)

    print("\nResultados guardados en results.json — correos en outbox/ (modo dry_run)")


if __name__ == "__main__":
    main()
