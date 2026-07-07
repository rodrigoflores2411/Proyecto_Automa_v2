"""
linkedin_source.py — Módulo de ingesta de candidatos desde LinkedIn.

LinkedIn tiene una API oficial (LinkedIn Talent Solutions) que requiere
aprobación como empresa. Este módulo implementa:
  1. MockLinkedInSource — simula perfiles reales (para desarrollo/demo)
  2. LinkedInSource     — estructura lista para conectar la API real

Para usar la API real, necesitas:
  - Cuenta LinkedIn Recruiter o LinkedIn Talent Hub
  - Credenciales OAuth 2.0 en developers.linkedin.com
"""

import uuid
import json
from dataclasses import dataclass
from typing import Optional
from .schemas import CandidateProfile


# ─────────────────────────── Estructura de perfil LinkedIn ──────────────────

@dataclass
class LinkedInProfile:
    """Perfil raw de LinkedIn antes de transformarlo a CandidateProfile."""
    linkedin_id:  str
    full_name:    str
    headline:     str          # "Senior Backend Developer at Empresa X"
    email:        str
    phone:        str
    location:     str
    summary:      str          # Sección "Acerca de"
    experience:   list[dict]   # Lista de trabajos
    education:    list[dict]   # Lista de estudios
    skills:       list[str]
    profile_url:  str
    connections:  int


# ─────────────────────────── Transformador LinkedIn → CandidateProfile ──────

def linkedin_to_candidate(profile: LinkedInProfile, position: str) -> CandidateProfile:
    """
    Transforma un perfil de LinkedIn al formato CandidateProfile del sistema.
    Calcula años de experiencia sumando duración de trabajos relevantes.
    """
    # Calcular años de experiencia total
    total_months = 0
    for exp in profile.experience:
        total_months += exp.get("duration_months", 12)
    years_exp = max(total_months // 12, 0)

    # Construir CV text desde experiencia + summary
    cv_parts = [profile.summary] if profile.summary else []
    for exp in profile.experience:
        cv_parts.append(
            f"{exp.get('title', '')} en {exp.get('company', '')} "
            f"({exp.get('duration_months', 0)//12} años): {exp.get('description', '')}"
        )

    # Educación principal (la más reciente)
    education_str = "No especificada"
    if profile.education:
        edu = profile.education[0]
        education_str = f"{edu.get('degree', '')} — {edu.get('institution', '')}"

    return CandidateProfile(
        candidate_id = f"LI-{profile.linkedin_id}",
        name         = profile.full_name,
        email        = profile.email,
        phone        = profile.phone,
        position     = position,
        years_exp    = years_exp,
        skills       = profile.skills,
        education    = education_str,
        cv_text      = "\n".join(cv_parts),
    )


# ─────────────────────────── Mock LinkedIn (para demo) ──────────────────────

class MockLinkedInSource:
    """
    Simula la respuesta de LinkedIn para demos y pruebas.
    En producción, reemplazar por LinkedInSource con OAuth real.
    """

    MOCK_PROFILES = [
        LinkedInProfile(
            linkedin_id  = "li-001",
            full_name    = "Rodrigo Quispe Mendoza",
            headline     = "Backend Developer | Python & FastAPI | 5 años exp.",
            email        = "rodrigo.quispe@gmail.com",
            phone        = "+51 944 123 456",
            location     = "Trujillo, La Libertad, Perú",
            summary      = (
                "Desarrollador backend especializado en Python y microservicios. "
                "5 años construyendo APIs REST con FastAPI y PostgreSQL. "
                "Experiencia en Docker, CI/CD con GitHub Actions y AWS. "
                "Apasionado por el código limpio y las buenas prácticas."
            ),
            experience   = [
                {
                    "title":           "Backend Developer Senior",
                    "company":         "TechPeru SAC",
                    "duration_months": 36,
                    "description":     "Desarrollo de microservicios con FastAPI y PostgreSQL. Lideré migración a Docker.",
                },
                {
                    "title":           "Backend Developer Junior",
                    "company":         "Startup Innovate",
                    "duration_months": 24,
                    "description":     "APIs REST con Django. Integración con pasarelas de pago.",
                },
            ],
            education    = [
                {
                    "degree":      "Ingeniería de Sistemas",
                    "institution": "Universidad Nacional de Trujillo",
                    "year":        2018,
                },
            ],
            skills       = ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "AWS", "Git"],
            profile_url  = "https://linkedin.com/in/rodrigo-quispe",
            connections  = 342,
        ),
        LinkedInProfile(
            linkedin_id  = "li-002",
            full_name    = "Valeria Torres Sánchez",
            headline     = "Data Analyst | Power BI | SQL | Python",
            email        = "valeria.torres@outlook.com",
            phone        = "+51 955 789 012",
            location     = "Lima, Perú",
            summary      = (
                "Analista de datos con 2 años de experiencia en BI y visualización. "
                "Construí dashboards en Power BI para el área comercial de retail. "
                "Manejo Python (Pandas, Matplotlib) para ETL y análisis exploratorio."
            ),
            experience   = [
                {
                    "title":           "Analista de Datos",
                    "company":         "RetailPeru",
                    "duration_months": 24,
                    "description":     "Dashboards en Power BI. ETL con Python. Reportes SQL semanales.",
                },
            ],
            education    = [
                {
                    "degree":      "Ingeniería Estadística",
                    "institution": "Pontificia Universidad Católica del Perú",
                    "year":        2022,
                },
            ],
            skills       = ["Python", "SQL", "Power BI", "Excel", "Pandas", "Tableau"],
            profile_url  = "https://linkedin.com/in/valeria-torres-data",
            connections  = 218,
        ),
        LinkedInProfile(
            linkedin_id  = "li-003",
            full_name    = "Miguel Castillo Reyes",
            headline     = "Estudiante de Ingeniería | Buscando primera oportunidad",
            email        = "miguel.castillo@upao.edu.pe",
            phone        = "+51 966 345 678",
            location     = "Trujillo, Perú",
            summary      = "Estudiante de último ciclo de Ingeniería de Sistemas. Conocimientos básicos de Python.",
            experience   = [],
            education    = [
                {
                    "degree":      "Ingeniería de Sistemas (en curso)",
                    "institution": "Universidad Privada Antenor Orrego",
                    "year":        2025,
                },
            ],
            skills       = ["Python básico", "HTML", "Excel"],
            profile_url  = "https://linkedin.com/in/miguel-castillo-upao",
            connections  = 45,
        ),
    ]

    def get_profiles_for_position(self, position: str) -> list[LinkedInProfile]:
        """Retorna perfiles mock simulando una búsqueda por posición."""
        print(f"[LINKEDIN] Buscando candidatos para: '{position}' (modo mock)")
        return self.MOCK_PROFILES

    def get_candidates(self, position: str) -> list[CandidateProfile]:
        """Retorna candidatos listos para el pipeline."""
        profiles = self.get_profiles_for_position(position)
        candidates = [linkedin_to_candidate(p, position) for p in profiles]
        print(f"[LINKEDIN] {len(candidates)} candidatos importados desde LinkedIn")
        return candidates


# ─────────────────────────── LinkedIn Real (estructura OAuth) ───────────────

class LinkedInSource:
    """
    Conector real con LinkedIn API (requiere aprobación en developers.linkedin.com).
    Reemplaza MockLinkedInSource cuando tengas credenciales.
    """

    BASE_URL = "https://api.linkedin.com/v2"

    def __init__(self, access_token: str):
        """
        access_token: Token OAuth 2.0 obtenido desde LinkedIn OAuth flow.
        Ver: https://developers.linkedin.com/docs/oauth2
        """
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json",
        }

    def search_candidates(self, keywords: str, location: str = "Peru") -> list[dict]:
        """
        Busca candidatos usando LinkedIn Talent Solutions API.
        Requiere plan LinkedIn Recruiter.
        Endpoint: POST /talentSearch
        """
        import requests
        # En producción, aquí va la llamada real:
        # response = requests.post(
        #     f"{self.BASE_URL}/talentSearch",
        #     headers=self.headers,
        #     json={"keywords": keywords, "location": location}
        # )
        # return response.json().get("elements", [])
        raise NotImplementedError(
            "Conecta tu access_token OAuth de LinkedIn Recruiter. "
            "Ver: https://developers.linkedin.com/docs/talent-solutions"
        )
