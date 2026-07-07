"""
langsmith_eval.py — Evaluación automatizada con LangSmith (documento §5.3.2,
§5.3.3). Sube el golden set como Dataset de LangSmith, ejecuta el grafo sobre
cada ejemplo y corre evaluadores automáticos, dejando un experimento
comparable en el proyecto de LangSmith configurado por variables de entorno.

Uso:
    python -m eval.langsmith_eval

Requiere LANGSMITH_API_KEY y LANGSMITH_TRACING=true en .env (§6 del README).
Si no hay credenciales de LangSmith, corre en modo local (sin subir dataset)
y solo imprime el resumen de evaluadores por consola — así el proyecto sigue
siendo reproducible sin depender de una cuenta externa.
"""

import os
from dotenv import load_dotenv

load_dotenv()

from langsmith import Client
from langsmith.evaluation import evaluate

from agents.graph import build_graph
from eval.golden_set import GOLDEN_SET, JOB_REQUIREMENTS

DATASET_NAME = "reclutamiento-golden-set-v1"


# ─────────────────────────── Evaluadores ───────────────────────────

def eval_validacion_correcta(run, example) -> dict:
    """¿El agente decidió is_valid igual a lo esperado? (§5.2 Exactitud)"""
    expected = example.outputs["expected_is_valid"]
    actual = run.outputs.get("is_valid")
    return {"key": "validacion_correcta", "score": float(actual == expected)}


def eval_decision_correcta(run, example) -> dict:
    """¿La decisión final (APPROVED/REJECTED) coincide con la esperada,
    cuando el caso no es de frontera (expected_decision no es None)?"""
    expected = example.outputs.get("expected_decision")
    if expected is None:
        return {"key": "decision_correcta", "score": None}  # caso de frontera/HITL, se excluye
    actual = run.outputs.get("decision")
    return {"key": "decision_correcta", "score": float(actual == expected)}


def eval_robustez_estructural(run, example) -> dict:
    """¿El grafo terminó sin excepción no manejada y produjo salida
    estructurada válida? (§5.2 Robustez, mapea a RNF de Pydantic)"""
    has_error = bool(run.error)
    has_output = bool(run.outputs)
    return {"key": "robustez_estructural", "score": float(not has_error and has_output)}


def eval_uso_de_rag(run, example) -> dict:
    """¿El nodo de evaluación efectivamente recuperó y usó contexto RAG
    (no es el string vacío por defecto)? Mide adopción real del subsistema RAG."""
    ctx = run.outputs.get("rag_context_used", "")
    used = bool(ctx) and "Sin políticas adicionales" not in ctx
    return {"key": "uso_de_rag", "score": float(used)}


EVALUATORS = [
    eval_validacion_correcta,
    eval_decision_correcta,
    eval_robustez_estructural,
    eval_uso_de_rag,
]


# ─────────────────────────── Target function ───────────────────────────

def _run_pipeline(inputs: dict) -> dict:
    """Wrapper que LangSmith invoca por cada ejemplo del dataset."""
    app = build_graph(checkpoint_db_path=":memory:")
    candidate = inputs["candidate"]
    config = {"configurable": {"thread_id": f"eval-{candidate.candidate_id}"}}
    state = {"candidate": candidate, "job_requirements": JOB_REQUIREMENTS}

    for _ in app.stream(state, config=config, stream_mode="values"):
        pass

    final = app.get_state(config)
    return dict(final.values)


# ─────────────────────────── Construcción del dataset ───────────────────────────

def _ensure_dataset(client: Client):
    existing = list(client.list_datasets(dataset_name=DATASET_NAME))
    if existing:
        return existing[0]

    dataset = client.create_dataset(dataset_name=DATASET_NAME, description=(
        "Golden set del sistema de reclutamiento (§5.1): 5 casos, incluye "
        "flujo feliz, promedio, débil y 2 adversariales."
    ))
    for case in GOLDEN_SET:
        client.create_example(
            inputs={"candidate": case["candidate"]},
            outputs={
                "expected_is_valid": case["expected_is_valid"],
                "expected_decision": case["expected_decision"],
                "case_type": case["case_type"],
            },
            dataset_id=dataset.id,
        )
    return dataset


def main():
    has_langsmith = bool(os.getenv("LANGSMITH_API_KEY"))

    if not has_langsmith:
        print("[WARN] LANGSMITH_API_KEY no configurada. Corriendo evaluación LOCAL "
              "(sin subir dataset ni experimento a LangSmith).")
        for case in GOLDEN_SET:
            out = _run_pipeline({"candidate": case["candidate"]})
            print(f"  {case['candidate'].candidate_id} ({case['case_type']}): "
                  f"is_valid={out.get('is_valid')} decision={out.get('decision')} "
                  f"rag_usado={'Sí' if out.get('rag_context_used') else 'No'}")
        return

    client = Client()
    dataset = _ensure_dataset(client)

    results = evaluate(
        _run_pipeline,
        data=dataset.name,
        evaluators=EVALUATORS,
        experiment_prefix="reclutamiento-deepagent",
        metadata={"model": "llama-3.3-70b-versatile", "prompt_version": "v1"},
    )
    print(f"\n✅ Experimento subido a LangSmith: {results}")
    print("   Revisa el proyecto en https://smith.langchain.com para comparar "
          "contra el experimento baseline (§5.3.3 Comparación de experimentos).")


if __name__ == "__main__":
    main()
