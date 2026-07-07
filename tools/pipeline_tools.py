"""
pipeline_tools.py — Implementación de las 4 tools documentadas en §3.4:
fetch_linkedin_profile, verify_sunedu_credentials, send_recruitment_email,
save_pipeline_report.
"""

import json
import os
import time
from pathlib import Path

from shared.linkedin_source import MockLinkedInSource
from shared.sunedu_validator import SUNEDUValidator


def fetch_linkedin_profile(position: str) -> list[dict]:
    """Ficha §3.4 — Ingesta de perfiles. Devuelve candidatos listos para el pipeline.
    Usa MockLinkedInSource (fuera del alcance del proyecto la API real OAuth, §2.2)."""
    source = MockLinkedInSource()
    candidates = source.get_candidates(position)
    return [c.to_dict() for c in candidates]


def verify_sunedu_credentials(dni: str, expected_institution: str = "") -> dict:
    """Ficha §3.4 — Validación de datos del candidato vía SUNEDU."""
    use_mock = os.getenv("SUNEDU_USE_MOCK", "true").lower() == "true"
    validator = SUNEDUValidator(use_mock=use_mock)
    result = validator.verify_by_dni(dni, expected_institution)
    return {
        "is_verified": result.found and result.verified,
        "found": result.found,
        "degrees": result.degrees,
        "institution": result.institution,
        "summary": validator.get_summary(result),
    }


def send_recruitment_email(recipient_email: str, subject: str, body: str) -> bool:
    """Ficha §3.4 — Envío de correos. En modo dry_run solo guarda el correo en disco
    (no requiere credenciales SMTP para reproducir el proyecto)."""
    mode = os.getenv("EMAIL_SEND_MODE", "dry_run")
    outbox = Path("outbox")
    outbox.mkdir(exist_ok=True)
    filename = outbox / f"{recipient_email.replace('@', '_at_')}_{int(time.time())}.txt"
    filename.write_text(f"Para: {recipient_email}\nAsunto: {subject}\n\n{body}", encoding="utf-8")

    if mode == "dry_run":
        print(f"  [EMAIL - dry_run] Guardado en {filename}")
        return True

    # --- Integración real (requiere credenciales en .env, ver .env.example) ---
    # import smtplib
    # from email.mime.text import MIMEText
    # msg = MIMEText(body)
    # msg["Subject"] = subject
    # msg["From"] = os.getenv("SMTP_USER")
    # msg["To"] = recipient_email
    # with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", 587))) as s:
    #     s.starttls()
    #     s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
    #     s.send_message(msg)
    raise NotImplementedError(
        "EMAIL_SEND_MODE distinto de 'dry_run': configura credenciales SMTP/SendGrid "
        "en .env y descomenta la integración real en pipeline_tools.py"
    )


def save_pipeline_report(candidate_id: str, report_data: dict) -> str:
    """Ficha §3.4 — Reporte de pruebas. Persiste el informe final en results.json."""
    path = Path("results.json")
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data[candidate_id] = report_data
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(path.resolve())
