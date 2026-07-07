# Sistema Multiagente de Reclutamiento — Migración a Deep Agent (LangGraph)

Migración del sistema original (`agents/orchestrator.py` + `ThreadPoolExecutor` + `SharedState`
con `RLock`) al patrón **Deep Agent construido sobre LangGraph**, documentado en el
Documento de Diseño §3.5–§3.6. Mantiene la misma lógica de negocio (6 responsabilidades
únicas, criterios de evaluación, escala de clasificación A+/A/B/C/D) pero reemplaza la
infraestructura de orquestación.

## Qué cambió respecto al proyecto original

| Antes | Ahora |
|---|---|
| `SharedState` + `RLock` manual | Estado tipado (`RecruitmentState`) gestionado por LangGraph |
| `ThreadPoolExecutor` para el swarm | Fan-out nativo de LangGraph (Comunicación ‖ FollowUp) |
| Sin checkpointing (se pierde todo si se cae el proceso) | `SqliteSaver` — reanudable por `thread_id = candidate_id` |
| Parseo manual de JSON con regex (`_extract_json`) | Salida estructurada obligatoria con Pydantic (`.with_structured_output`) |
| Sin pausa para revisión humana | Interrupción (HITL) automática en casos frontera (score 50-59 o SUNEDU no verificado) |
| API key de Groq embebida en el código | Variables de entorno vía `.env` |
| RAG no implementado ("no aplica" en el documento v3) | `shared/rag_kb.py` + `tools/rag_tools.py`: retrieval BM25 real, usado en `evaluar_clasificar` |
| Sin pruebas automatizadas | `tests/test_graph.py` (12 pruebas, sin LLM) + `eval/langsmith_eval.py` (evaluación con LLM) |
| Sin CI/CD | `.github/workflows/ci.yml`: pytest + ruff en cada push, evaluación LangSmith en `main` |

## 1. Requisitos

- Python 3.11+
- Una cuenta gratuita en [Groq Console](https://console.groq.com/keys) (LLM)
- (Opcional pero recomendado) Cuenta gratuita en [LangSmith](https://smith.langchain.com/settings) para trazas/evaluación (§5.3 del documento)

## 2. Instalación

```bash
# 1. Ubicarte en la carpeta del proyecto
cd deepagent

# 2. Crear entorno virtual (recomendado)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

## 3. Configurar credenciales

```bash
cp .env.example .env
```

Edita `.env` y completa como mínimo:

```env
GROQ_API_KEY=gsk_tu_api_key_aqui
```

Todo lo demás (`LANGSMITH_*`, `SUNEDU_USE_MOCK`, `EMAIL_SEND_MODE`) ya viene con valores
por defecto que permiten ejecutar el proyecto completo **sin ninguna otra credencial**:
SUNEDU corre en modo simulado y los correos se guardan en `outbox/` en vez de enviarse.

Cómo obtener cada credencial:

- **GROQ_API_KEY** (obligatoria): [console.groq.com/keys](https://console.groq.com/keys) → "Create API Key". Plan gratuito, sin tarjeta.
- **LANGSMITH_API_KEY** (opcional, para observabilidad §5.3): [smith.langchain.com/settings](https://smith.langchain.com/settings) → "Create API Key".

## 4. Ejecutar el pipeline

```bash
python main.py
```

Esto procesa los candidatos de ejemplo (equivalentes a los casos C001 y C004 del golden
set, §5.1) y genera:

- `checkpoints.sqlite` — estado persistido del grafo (reanudable).
- `results.json` — informe de cierre por candidato.
- `outbox/*.txt` — correos generados (modo `dry_run`, no requiere SMTP).

## 5. Human-in-the-loop (HITL)

Si un candidato cae en la banda frontera (score 50-59) o SUNEDU no pudo verificar su
título, el grafo se pausa automáticamente:

```
⏸  PAUSADO para revisión humana (HITL). Nodo pendiente: ('evaluar_clasificar',)
```

Para inspeccionar y luego continuar el pipeline de ese candidato:

```python
from agents.graph import build_graph
app = build_graph()
config = {"configurable": {"thread_id": "C00X"}}

print(app.get_state(config).values)   # revisar el estado antes de aprobar

app.invoke(None, config=config)       # continúa el grafo desde donde se pausó
```

## 6. Activar trazas de LangSmith (opcional)

Con `LANGSMITH_TRACING=true` y `LANGSMITH_API_KEY` configurados en `.env`, cada corrida
queda trazada automáticamente en tu proyecto de LangSmith — no requiere código adicional
(`load_dotenv()` en `main.py` ya expone las variables al SDK de LangChain).

## 6.1 Subsistema RAG

`shared/rag_kb.py` indexa 5 documentos de políticas de RRHH (equivalencias de
experiencia, certificaciones, brechas críticas vs. secundarias) con **BM25**
(`rank_bm25`, sin dependencias de embeddings/GPU). El nodo `evaluar_clasificar`
en `agents/graph.py` recupera las 2 políticas más relevantes al puesto y las
inyecta en el prompt de evaluación **como fuente de verdad institucional**,
antes de que el LLM puntúe al candidato. Es trazable: el campo `rag_context_used`
queda en el estado final y se audita en `results.json`.

## 6.2 Pruebas y evaluación continua

```bash
# Pruebas unitarias deterministas (sin LLM, sin costo de tokens)
pytest tests/ -v

# Evaluación con LLM sobre el golden set completo (§5.1), sube dataset +
# experimento a LangSmith si hay credenciales; si no, corre en modo local
python -m eval.langsmith_eval
```

`eval/langsmith_eval.py` define 4 evaluadores automáticos: `validacion_correcta`,
`decision_correcta` (excluye casos de frontera/HITL), `robustez_estructural` y
`uso_de_rag` (mide adopción real del subsistema RAG, no solo si existe el código).

## 7. Estructura del proyecto

```
deepagent/
├── main.py                    # Punto de entrada
├── requirements.txt
├── .env.example                # Plantilla de credenciales
├── shared/
│   ├── schemas.py              # CandidateProfile + esquemas Pydantic (§3.7)
│   ├── state.py                 # RecruitmentState (TypedDict, §3.5)
│   ├── sunedu_validator.py      # Validador SUNEDU (migrado sin cambios)
│   └── linkedin_source.py       # Mock de ingesta LinkedIn (migrado sin cambios)
├── agents/
│   ├── prompts.py               # Catálogo de prompts v1 (§6)
│   └── graph.py                 # Construcción del StateGraph (§3.5, §3.6)
├── tools/
│   ├── pipeline_tools.py        # Las 4 tools documentadas en §3.4
│   └── rag_tools.py             # Tool de recuperación RAG (§3.3, §3.4)
├── eval/
│   ├── golden_set.py            # Datos del golden set (§5.1), reutilizados
│   └── langsmith_eval.py        # Dataset + evaluadores + experimento (§5.3)
├── tests/
│   └── test_graph.py            # 12 pruebas deterministas (§5, calidad de código)
└── .github/workflows/ci.yml     # CI: pytest + ruff + evaluación LangSmith en main
```

## 8. Despliegue (§8.3 del documento)

Opción elegida: **LangGraph Platform (cloud)**. Pasos generales:

```bash
pip install langgraph-cli
langgraph build      # empaqueta el grafo definido en agents/graph.py
langgraph deploy     # requiere cuenta en https://smith.langchain.com (LangGraph Platform)
```

Configura las mismas variables de `.env` como *secrets* del entorno de despliegue
(nunca las subas al repositorio — `.env` ya está listado en `.gitignore`).

## 9. Notas de seguridad (§3.9 del documento)

- La API key ya NO está hardcodeada en el código (a diferencia de `base_agent.py`
  del proyecto original, que la tenía expuesta dentro de `os.getenv("gsk_...")`).
- El DNI, teléfono y correo se usan solo para las tools deterministas (SUNEDU, envío de
  correo); no se envían como texto libre adicional al prompt del LLM más allá de lo
  necesario para la evaluación.
