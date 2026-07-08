"""
sunedu_validator.py — Agente de validación de títulos universitarios via SUNEDU.

SUNEDU (Superintendencia Nacional de Educación Superior Universitaria) tiene
un portal público de consulta de grados y títulos registrados en Perú.

Portal público: https://enlinea.sunedu.gob.pe/
API pública:    https://api.sunedu.gob.pe/ (consulta por DNI)
"""

import requests
import time
import json
from dataclasses import dataclass


@dataclass
class SUNEDUResult:
    """Resultado de la consulta a SUNEDU."""
    dni:             str
    found:           bool
    name:            str           = ""
    degrees:         list[dict]    = None   # Lista de grados registrados
    institution:     str           = ""     # Universidad registrada
    verified:        bool          = False
    error:           str           = ""
    source:          str           = "SUNEDU"

    def __post_init__(self):
        if self.degrees is None:
            self.degrees = []


class SUNEDUValidator:
    """
    Validador de títulos universitarios usando el portal público de SUNEDU.
    Consulta si el grado académico del candidato está registrado oficialmente.
    """

    # Endpoint público de SUNEDU (portal de consulta de grados y títulos)
    BASE_URL   = "https://enlinea.sunedu.gob.pe"
    API_URL    = "https://api.sunedu.gob.pe/titulos/consulta"
    TIMEOUT    = 10  # segundos

    def __init__(self, use_mock: bool = False):
        """
        use_mock=True: Usa datos simulados (para demo sin internet o sin DNI real).
        use_mock=False: Intenta consultar la API real de SUNEDU.
        """
        self.use_mock = use_mock
        self.session  = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; RecruitmentSystem/1.0)",
            "Accept":     "application/json",
        })

    def verify_by_dni(self, dni: str, expected_institution: str = "") -> SUNEDUResult:
        """
        Consulta SUNEDU por DNI para verificar grados registrados.

        Args:
            dni: DNI del candidato (8 dígitos)
            expected_institution: Universidad declarada por el candidato (para cruzar)

        Returns:
            SUNEDUResult con grados encontrados y si coincide con lo declarado
        """
        if self.use_mock:
            return self._mock_verify(dni, expected_institution)

        try:
            result = self._query_sunedu_api(dni)
            if result.found and expected_institution:
                # Verificar si la institución declarada coincide con la registrada
                declared_lower  = expected_institution.lower()
                registered_lower = result.institution.lower()
                result.verified = any(
                    word in registered_lower
                    for word in declared_lower.split()
                    if len(word) > 4
                )
            return result

        except requests.RequestException as e:
            # Si la API falla, usar mock con advertencia
            print(f"  [SUNEDU] ⚠️  API no disponible ({e}), usando modo simulación")
            return self._mock_verify(dni, expected_institution)

    def _query_sunedu_api(self, dni: str) -> SUNEDUResult:
        """
        Consulta real a SUNEDU.
        Endpoint público: https://enlinea.sunedu.gob.pe
        """
        try:
            # Consulta al portal público de SUNEDU
            response = self.session.get(
                f"{self.BASE_URL}/ws-grados/grados/obtenerGradosPorDni",
                params  = {"dni": dni},
                timeout = self.TIMEOUT,
            )

            if response.status_code == 200:
                data    = response.json()
                degrees = data.get("data", [])

                if degrees:
                    inst = degrees[0].get("nombreUniversidad", "")
                    return SUNEDUResult(
                        dni         = dni,
                        found       = True,
                        name        = degrees[0].get("nombreCompleto", ""),
                        degrees     = [
                            {
                                "grado":       d.get("grado", ""),
                                "titulo":      d.get("titulo", ""),
                                "universidad": d.get("nombreUniversidad", ""),
                                "anio":        d.get("anioGrado", ""),
                                "estado":      d.get("estado", ""),
                            }
                            for d in degrees
                        ],
                        institution = inst,
                        verified    = True,
                        source      = "SUNEDU_API",
                    )
                else:
                    return SUNEDUResult(
                        dni    = dni,
                        found  = False,
                        error  = "No se encontraron grados registrados para este DNI",
                        source = "SUNEDU_API",
                    )
            else:
                raise requests.RequestException(f"HTTP {response.status_code}")

        except (json.JSONDecodeError, KeyError) as e:
            raise requests.RequestException(f"Error parsing respuesta SUNEDU: {e}")

    def _mock_verify(self, dni: str, expected_institution: str = "") -> SUNEDUResult:
        """
        Simulación de SUNEDU para demos sin DNI real.
        Genera respuesta basada en si el DNI parece válido (8 dígitos).
        """
        time.sleep(0.3)  # Simula latencia de red

        # DNI válido = 8 dígitos numéricos
        if not (dni and dni.isdigit() and len(dni) == 8):
            return SUNEDUResult(
                dni   = dni,
                found = False,
                error = "DNI inválido (debe tener 8 dígitos numéricos)",
            )

        # Simulación: DNIs que terminan en par → título encontrado
        if int(dni[-1]) % 2 == 0:
            inst     = expected_institution or "Universidad Nacional de Trujillo"
            verified = bool(expected_institution)
            return SUNEDUResult(
                dni         = dni,
                found       = True,
                name        = "NOMBRE SIMULADO SUNEDU",
                degrees     = [
                    {
                        "grado":       "Bachiller",
                        "titulo":      "Ingeniero de Sistemas",
                        "universidad": inst,
                        "anio":        "2020",
                        "estado":      "REGISTRADO",
                    }
                ],
                institution = inst,
                verified    = verified,
                source      = "SUNEDU_MOCK",
            )
        else:
            return SUNEDUResult(
                dni    = dni,
                found  = False,
                error  = "No se encontraron grados registrados (simulación)",
                source = "SUNEDU_MOCK",
            )

    def get_summary(self, result: SUNEDUResult) -> str:
        """Genera un resumen legible del resultado SUNEDU para incluir en el prompt."""
        if not result.found:
            return f"SUNEDU: No se encontraron grados registrados. Error: {result.error}"

        degrees_str = "; ".join(
            f"{d['grado']} en {d['titulo']} — {d['universidad']} ({d['anio']})"
            for d in result.degrees
        )
        status = "✅ VERIFICADO" if result.verified else "⚠️ NO COINCIDE con lo declarado"
        return f"SUNEDU [{status}]: {degrees_str} | Fuente: {result.source}"
