from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import io
import json
import time

from shared.schemas import CandidateProfile
from agents.graph import build_graph

load_dotenv()

app = FastAPI(
    title="Sistema Multiagente de Reclutamiento",
    version="2.0",
    description="Deep Agents + LangGraph + Groq"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
    return {"status": "healthy"}


@app.post("/parse-cv")
async def parse_cv(file: UploadFile = File(...)):
    """
    Recibe un PDF de CV, extrae el texto y usa Groq para
    devolver los campos del candidato en formato JSON.
    """
    # ── 1. Validar tipo de archivo ──────────────────────────────────────────
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF.")

    # ── 2. Extraer texto del PDF ────────────────────────────────────────────
    try:
        import pypdf
        content = await file.read()
        reader = pypdf.PdfReader(io.BytesIO(content))
        cv_text = "\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"No se pudo leer el PDF: {e}")

    if not cv_text:
        raise HTTPException(status_code=422, detail="El PDF no contiene texto extraíble.")

    # ── 3. Llamar a Groq para extraer campos estructurados ─────────────────
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        # Sin API key: devolver solo el texto para que el usuario llene los campos
        return JSONResponse(content={"cv_text": cv_text, "extracted": {}})

    try:
        from groq import Groq
        client = Groq(api_key=groq_key)

        prompt = f"""Analiza el siguiente texto de un CV y extrae la información del candidato.
Devuelve ÚNICAMENTE un objeto JSON válido con exactamente estas claves (sin explicaciones adicionales):

{{
  "name": "Nombre completo del candidato",
  "email": "correo@ejemplo.com",
  "phone": "+51 999 000 000",
  "position": "Puesto al que postula o puesto actual",
  "years_exp": 5,
  "skills": ["Python", "FastAPI"],
  "education": "Grado o título académico",
  "dni": "DNI si aparece, si no null"
}}

Si un campo no está en el CV, usa null para strings y 0 para números.
Skills debe ser una lista de tecnologías/herramientas concretas.

CV:
---
{cv_text[:4000]}
---

JSON:"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=600,
        )

        raw = response.choices[0].message.content.strip()

        # Limpiar posibles markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        extracted = json.loads(raw)

    except json.JSONDecodeError:
        extracted = {}
    except Exception as e:
        extracted = {"_error": str(e)}

    return JSONResponse(content={
        "cv_text": cv_text[:6000],
        "extracted": extracted
    })


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