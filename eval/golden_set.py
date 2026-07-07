"""
golden_set.py — Conjunto de evaluación (documento §5.1), como datos puros
para reutilizarlos tanto en pytest (tests/) como en el dataset de LangSmith
(eval/langsmith_eval.py), evitando duplicar los casos de prueba.
"""

from shared.schemas import CandidateProfile

JOB_REQUIREMENTS = {
    "position": "Desarrollador Backend Senior",
    "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "min_years_exp": 4,
    "education": "Ingeniería de Sistemas",
    "description": "Backend developer con experiencia en microservicios.",
}

# Cada caso incluye el resultado ESPERADO para poder evaluarlo automáticamente
# (evaluadores en eval/langsmith_eval.py y asserts en tests/test_graph.py).
GOLDEN_SET = [
    {
        "candidate": CandidateProfile(
            candidate_id="C001", name="Ana García", email="ana.garcia@email.com",
            phone="+51 999 111 111", position="Desarrollador Backend Senior", years_exp=6,
            skills=["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes"],
            education="Ingeniería de Sistemas", dni="12345678",
            cv_text="6 años de experiencia liderando equipos backend con Python y FastAPI. "
                    "Experta en PostgreSQL, Docker y Kubernetes en producción.",
        ),
        "expected_is_valid": True,
        "expected_decision": "APPROVED",
        "case_type": "estandar_fuerte",
    },
    {
        "candidate": CandidateProfile(
            candidate_id="C002", name="Carlos Mendoza", email="c.mendoza@gmail.com",
            phone="+51 988 333 444", position="Desarrollador Backend Senior", years_exp=3,
            skills=["Python", "Django", "MySQL", "Git"],
            education="Ingeniería de Software", dni="23456789",
            cv_text="Desarrollador Python con 3 años de experiencia en Django. "
                    "Proyectos de e-commerce de tamaño mediano.",
        ),
        "expected_is_valid": True,
        "expected_decision": None,  # frontera, puede pausar en HITL
        "case_type": "estandar_promedio",
    },
    {
        "candidate": CandidateProfile(
            candidate_id="C003", name="Pedro Alvarado", email="pedro@correo.com",
            phone="+51 977 555 666", position="Desarrollador Backend Senior", years_exp=1,
            skills=["HTML", "CSS", "Excel"],
            education="Técnico en Computación", dni="34567890",
            cv_text="Tengo conocimientos básicos de computación y he hecho páginas "
                    "web sencillas con HTML.",
        ),
        "expected_is_valid": True,
        "expected_decision": "REJECTED",
        "case_type": "estandar_debil",
    },
    {
        "candidate": CandidateProfile(
            candidate_id="C004", name="María Torres", email="sin-arroba-email",
            phone="", position="Desarrollador Backend Senior", years_exp=1,
            skills=[], education="", dni="",
            cv_text="Soy dev.",
        ),
        "expected_is_valid": False,
        "expected_decision": None,  # rechazo temprano, no llega a clasificación
        "case_type": "adversarial_datos_invalidos",
    },
    {
        "candidate": CandidateProfile(
            candidate_id="C005", name="Roberto Silva", email="roberto.silva@outlook.com",
            phone="+51 966 777 888", position="Desarrollador Backend Senior", years_exp=-3,
            skills=["Python", "SQL"], education="Ingeniería Estadística", dni="45678901",
            cv_text="Analista de datos con experiencia en Python y SQL.",
        ),
        "expected_is_valid": False,
        "expected_decision": None,
        "case_type": "adversarial_edge_case_negativo",
    },
]
