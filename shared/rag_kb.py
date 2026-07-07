"""
rag_kb.py — Subsistema RAG (documento §3.3, ahora implementado).

Base de conocimiento pequeña pero real: políticas internas de RRHH y
descripciones de puesto ampliadas de UPAO. Se indexa con BM25 (rank_bm25,
sin dependencias pesadas de embeddings/GPU) y se recupera el contexto más
relevante para enriquecer al EvaluationAgent con criterios que NO están en
el prompt estático (política de equivalencias de experiencia, tolerancias
de certificación, etc.), evitando alucinación de reglas de negocio.
"""

from dataclasses import dataclass
from rank_bm25 import BM25Okapi

# ─────────────────────────── Documentos fuente (KB) ───────────────────────────
# En producción esto vendría de Confluence/Notion/SharePoint de RRHH (§2.5).
DOCUMENTS: list[dict] = [
    {
        "id": "pol-001",
        "title": "Política de equivalencia de experiencia",
        "text": (
            "UPAO reconoce como experiencia válida los años trabajados en prácticas "
            "pre-profesionales a razón de 0.5 años por cada año de práctica, hasta un "
            "máximo de 1 año total. La experiencia freelance certificable (contratos, "
            "facturas) cuenta como experiencia laboral plena."
        ),
    },
    {
        "id": "pol-002",
        "title": "Política de certificaciones técnicas",
        "text": (
            "Certificaciones vigentes de AWS, Google Cloud o Azure equivalen a 6 meses "
            "adicionales de experiencia técnica en la evaluación de skills, siempre que "
            "el candidato las mencione explícitamente en su CV con fecha de vigencia."
        ),
    },
    {
        "id": "pol-003",
        "title": "Descripción ampliada — Desarrollador Backend Senior",
        "text": (
            "El puesto de Desarrollador Backend Senior requiere dominio de Python y "
            "al menos un framework async (FastAPI o Django async). Se valora "
            "experiencia con bases de datos relacionales (PostgreSQL) y contenedores "
            "(Docker/Kubernetes). No es excluyente la falta de Kubernetes si el "
            "candidato demuestra Docker sólido y disposición a aprender."
        ),
    },
    {
        "id": "pol-004",
        "title": "Descripción ampliada — Analista de Datos Junior",
        "text": (
            "El puesto de Analista de Datos Junior prioriza pensamiento analítico y "
            "SQL sobre el dominio de una herramienta de BI específica. Power BI y "
            "Tableau se consideran equivalentes entre sí para efectos de evaluación."
        ),
    },
    {
        "id": "pol-005",
        "title": "Política de brechas críticas vs. secundarias",
        "text": (
            "Una brecha se considera CRÍTICA si el requisito falta por completo y no "
            "existe evidencia de aprendizaje reciente (cursos, certificaciones en curso). "
            "Se considera SECUNDARIA si el candidato tiene una tecnología equivalente "
            "(ej. Django en vez de FastAPI) o evidencia de estar aprendiendo la brecha."
        ),
    },
]


@dataclass
class RetrievedChunk:
    doc_id: str
    title: str
    text: str
    score: float


class RAGRetriever:
    """Índice BM25 sobre la base de conocimiento de políticas de RRHH."""

    def __init__(self, documents: list[dict] = None):
        self.documents = documents or DOCUMENTS
        self._corpus_tokens = [self._tokenize(d["text"]) for d in self.documents]
        self._bm25 = BM25Okapi(self._corpus_tokens)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return text.lower().replace(",", "").replace(".", "").split()

    def retrieve(self, query: str, k: int = 2) -> list[RetrievedChunk]:
        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(zip(self.documents, scores), key=lambda x: x[1], reverse=True)
        return [
            RetrievedChunk(doc_id=d["id"], title=d["title"], text=d["text"], score=float(s))
            for d, s in ranked[:k]
            if s > 0
        ]

    def format_context(self, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return "Sin políticas adicionales relevantes."
        return "\n".join(f"- [{c.title}] {c.text}" for c in chunks)
