from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
import os

from shared.schemas import CandidateProfile
from agents.graph import build_graph

load_dotenv()

app = FastAPI(
    title="Sistema Multiagente de Reclutamiento",
    version="2.0",
    description="Deep Agents + LangGraph + Groq"
)

# Servir archivos estáticos (frontend)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

graph = build_graph(
    checkpoint_db_path="checkpoints.sqlite"
)
JOB_REQUIREMENTS = {
    "position": "Desarrollador Backend Senior",
    "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "min_years_exp": 4,
    "education": "Ingeniería de Sistemas",
    "description": "Backend developer con experiencia en microservicios."
}


@app.get("/")
def root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
    return {
        "status": "online",
        "project": "Proyecto Automa v2",
        "framework": "FastAPI",
        "graph": "LangGraph"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/evaluate")
def evaluate(candidate: CandidateProfile):

    config = {
        "configurable": {
            "thread_id": candidate.candidate_id
        }
    }

    initial_state = {
        "candidate": candidate,
        "job_requirements": JOB_REQUIREMENTS
    }

    try:

        for _ in graph.stream(
                initial_state,
                config=config,
                stream_mode="values"
        ):
            pass

        state = graph.get_state(config)

        return JSONResponse(
            content=jsonable_encoder({
                "candidate": candidate.name,
                "classification": state.values.get(
                    "classification",
                    "RECHAZO_TEMPRANO"
                ),
                "decision": state.values.get(
                    "decision",
                    state.values.get("validation_issues")
                ),
                "state": state.values
            })
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/metrics")
def metrics():

    return {
        "status": "running",
        "model": "llama-3.1-8b-instant",
        "provider": "Groq"
    }