"""
master_agent.py — LangGraph Master Agent with confidence scoring and multi-turn memory

LangGraph-based conversational agent that routes user questions to appropriate tools.
Supports confidence scoring for classifications and multi-turn conversations with session memory.

Architecture Overview:
- Central Orchestrator: Manages conversation flow between Phase 1 (Analysis) and Phase 2 (RAG)
- Task Routing: Classifies questions into two categories (analysis or RAG) via keyword + LLM
- Confidence Scoring: Measures classification certainty (keyword match strength, LLM fallback)
- Session Memory: Stores analysis results across multiple turns for context-aware follow-ups
- Tool Integration: Wraps analysis_tool and rag_tool in LangGraph workflow nodes
- State Management: AgentState flows through graph nodes, accumulating results
- Multi-Turn Ready: Preserves message history and analysis context for follow-up questions

LangGraph Workflow:
User Question → Classify → (Analysis | RAG) → Format → Answer

Four-Node Graph Architecture:
1. classify: Keyword-based + LLM-based task detection (analysis vs RAG) with confidence
2. route_task: Conditional routing node (sends to analysis or rag)
3. analysis: Phase 1 engine (AutoML/EDA/Anomaly detection)
4. rag: Phase 2 engine (PDF semantic search + LLM generation)
5. format: Add source citations and polish French response
6. END: Return final answer to user

Task Classification Strategy with Confidence Scoring:
- Primary: Keyword matching (fast, no LLM call) with scoring
  - Analysis keywords: "analyse", "csv", "dataset", "modèle", "anomalie", "ML"
  - RAG keywords: "rgpd", "cnil", "document", "pdf", "réglementation", "loi"
- Confidence: Based on keyword match strength (0.0-1.0)
  - Perfect match (one category dominates): confidence 0.95+
  - Marginal match (keywords present but weak): confidence 0.6-0.8
  - Ambiguous (tied scores): confidence 0.5 (triggers LLM classification)
  - LLM fallback: Reduces confidence to 0.7 (less certain than keyword match)
- Fallback: If keywords ambiguous (close scores), use LLM to classify
- Timeout Protection: LLM classification exception defaults to RAG (confidence 0.5)

Phase 1 — Analysis (CSV Data)
- Entry: User provides CSV file path + optional target column
- Pipeline: Load → EDA → AutoML+SHAP → Anomaly Detection
- Output: French narrative with insights, model performance, anomalies
- Performance: 10-40 seconds typical (AutoML dominated)

Phase 2 — RAG (PDF Documents)
- Entry: User question (auto-detects PDF corpus)
- Pipeline: Embed question → Semantic search → Prompt + LLM
- Output: French answer with source citations and page numbers
- Performance: 5-35 seconds typical (LLM generation dominated)

Multi-Turn Memory:
- Session Storage: In-memory dict storing analysis results per session_id
- Context Preservation: Follow-up questions can reference prior analysis
- Memory Structure: {session_id: {"analyses": [...], "timestamp": ...}}
- Usage: Augment classifier context and enable follow-up question understanding
- Example: Q1: "Analyse ce CSV" → Q2: "Quelles anomalies as-tu trouvé?" (references Q1)

Integration Points:
- Ollama: Local LLM inference (mistral-nemo for classification and RAG)
- PostgreSQL pgvector: Vector database for PDF embeddings
- LangChain: Chat models and message handling
- LangGraph: Workflow state machine and conditional routing
- Session Memory: Stores analysis results for multi-turn conversations

Error Handling Strategy:
- Pre-flight validation: Check question not empty
- Node-level try-catch: Each node handles internal errors
- Graceful degradation: Missing dataset/PDF returns helpful message, not crash
- Final catch: Agent.invoke() exception caught, returns error dict
- Logging: All steps logged (INFO for normal, WARNING for issues, ERROR for failures)
- Confidence: Even on errors, return confidence metric for classification

Performance Considerations:
- Classification: ~100-200ms (mostly keyword matching)
- Confidence scoring: <10ms (string operations)
- Analysis execution: 10-40 seconds (AutoML dominated)
- RAG execution: 5-35 seconds (LLM generation dominated)
- Total latency: ~5-50 seconds depending on task
- Scalability: Designed for single-threaded, sequential queries per user
- Memory: O(n) where n = number of sessions (typically <100 in practice)

Future Enhancements:
- Multi-turn conversations: Preserve message history for follow-up questions ✓ (started)
- Intent refining: Ask clarifying questions if classification confidence low
- Tool combination: Hybrid analysis + RAG for complex queries
- Streaming: Return partial answers as they become available
- Context windows: Support longer documents via chunking strategies
- Persistent memory: Database storage for cross-session analysis retrieval
"""

import logging
from typing import Literal
from langgraph.graph import StateGraph, END
import os
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage

from backend.agent.agent_state import AgentState
from backend.agent.tools.analysis_tool import run_analysis
from backend.agent.tools.rag_tool import ask_document, get_indexed_documents
from backend.utils.language import detect_language

logger = logging.getLogger(__name__)

# LLM Configuration
LLM_MODEL = "mistral-nemo:latest"
OLLAMA_URL = "http://localhost:11434"

# Confidence scoring thresholds
CONFIDENCE_HIGH = 0.90  # Strong keyword match or clear LLM classification
CONFIDENCE_MEDIUM = 0.70  # Moderate keyword match or LLM with context
CONFIDENCE_LOW = 0.50  # Ambiguous classification, triggers LLM fallback

# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-TURN SESSION MEMORY: Store analysis results across conversation turns
# ═══════════════════════════════════════════════════════════════════════════════
# Session storage: {session_id: {"analyses": [...], "timestamp": ..., "last_analysis": {...}}}
# Enables follow-up questions to reference prior analysis without re-running
SESSION_MEMORY = {}

def _get_session_memory(session_id: str) -> dict:
    """Retrieve or create session memory for multi-turn conversations.
    
    Args:
        session_id: Unique identifier for conversation session
    
    Returns:
        dict: Session memory object with analyses history
    """
    if session_id not in SESSION_MEMORY:
        SESSION_MEMORY[session_id] = {
            "analyses": [],  # List of past analysis results
            "last_analysis": None,  # Most recent analysis for context
            "timestamp": None  # Last memory update time
        }
    return SESSION_MEMORY[session_id]


def _store_analysis_in_memory(session_id: str, analysis_result: dict) -> None:
    """Store analysis result in session memory for follow-up questions.
    
    Args:
        session_id: Conversation session ID
        analysis_result: Complete analysis output from run_analysis()
    """
    memory = _get_session_memory(session_id)
    memory["analyses"].append({
        "timestamp": __import__("time").time(),
        "dataset_path": analysis_result.get("dataset_path"),
        "rows": analysis_result.get("rows"),
        "columns": analysis_result.get("columns"),
        "best_model": analysis_result.get("best_model"),
        "anomalies": analysis_result.get("anomalies", {}),
        "answer_excerpt": analysis_result.get("answer", "")[:200]  # Summary for context
    })
    memory["last_analysis"] = memory["analyses"][-1]
    logger.debug(f"Stored analysis in session memory: {session_id}")


def get_llm():
    """
    Get configured LLM instance for task classification and RAG.

    Configuration:
    - Model: mistral-nemo:latest (lightweight, ~7.3B parameters)
    - Temperature: 0.1 (low randomness, focused on factual outputs)
    - Base URL: http://localhost:11434 (Ollama API endpoint)

    Returns:
        ChatOllama: Configured LLM instance ready for inference

    Performance:
    - Initialization: ~100ms
    - First inference: ~2-3s (model loading in memory)
    - Subsequent inferences: ~1-2s per 100 tokens

    Error Handling:
    - Exception if Ollama server not running at base_url
    - Caller should wrap in try-catch for connection failures
    """
    provider = os.getenv("LLM_PROVIDER", "ollama")
    if provider == "groq":
        return ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1,
        )
    return ChatOllama(
        model=LLM_MODEL,
        base_url=OLLAMA_URL,
        temperature=0.1
    )


# ═══════════════════════════════════════════
# NODE 1 — Classify task type
# ═══════════════════════════════════════════

def classify_task(state: AgentState) -> AgentState:
    """
    NODE 1: Hybrid keyword + LLM-based task classification with confidence scoring.

    Determines whether user question routes to Phase 1 (analysis) or Phase 2 (RAG).
    Returns both task_type and confidence_score for quality metrics.

    Classification Strategy (2-stage with confidence):
    STAGE 1 — Keyword Matching (fast, <10ms):
    - Count analysis keywords: "analyse", "csv", "dataset", "données", "modèle", "anomalie", "ML"
    - Count RAG keywords: "rgpd", "cnil", "document", "pdf", "réglementation", "loi", "article"
    - If one category has clear lead (score difference > 0 with score > 0), use that category
    - Confidence calculation:
      * High (0.95+): Dominant keyword presence (5+ keywords from leading category)
      * Medium (0.75-0.85): Moderate keyword presence (2-4 keywords)
      * Low (0.50-0.70): Single keyword match or tied scores
    - If scores tied or both zero, proceed to Stage 2

    STAGE 2 — LLM Classification (if Stage 1 ambiguous):
    - Call mistral-nemo with explicit classification prompt
    - LLM analyzes semantics to disambiguate
    - Confidence reduced to 0.70 (less certain than keyword match)
    - Timeout/error defaults to 'rag' (safe fallback) with confidence 0.50

    Input State Fields Used:
    - question (str): User's question in French or English
    - session_id (str, optional): For multi-turn memory lookup

    Output State Changes:
    - task_type: Set to 'analysis' or 'rag'
    - confidence_score: Float 0.0-1.0 representing classification certainty
    - steps_taken: Appended with 'classify → {task_type} (conf={score:.2f})'

    Performance:
    - Stage 1 (keyword): ~5-10ms
    - Stage 2 (LLM fallback): ~1-2 seconds (if triggered)
    - Confidence calculation: <1ms
    - Typical total: <50ms for common keywords
    """
    question = state["question"]
    logger.info(f"Classifying task: {question[:80]}")

    # Detect language from original question before history appended
    original_question = question.split("\nPrécédente analyse:")[0].strip()
    language = detect_language(original_question)
    logger.info(f"Language detected: {language}")

    # ═══════════════════════════════════════════════════════════════════════════════
    # STAGE 1 — Keyword-based classification (fast, <10ms, no LLM call)
    # ═══════════════════════════════════════════════════════════════════════════════
    question_lower = question.lower()

    # Keywords indicating Phase 1 ANALYSIS: CSV files, data, statistics, ML
    # Note: use root/partial forms so conjugations and plurals match (e.g. "analys" → analysez/analyser/analyse)
    analysis_keywords = [
        "analys",          # covers: analyse, analyser, analysez, analysons
        "csv", "dataset", "données", "donnée", "colonnes",
        "modèle", "prédire", "prédiction", "ml", "machine learning",
        "anomalie", "anomalies", "détect",   # covers: détecte, détectées, détection
        "statistique", "corrélation", "régression", "classification",
        "fichier", "entraîne", "entraînement"
    ]

    # Keywords indicating Phase 2 RAG: PDFs, documents, compliance, regulations
    rag_keywords = [
        "rgpd", "cnil", "document", "pdf", "réglementation", "loi",
        "article", "règlement", "droit", "obligation", "conformité",
        "protection", "données personnelles", "open source", "ia"
    ]

    # Keywords indicating Phase 3 CODE: Code execution, scripting, programming
    code_keywords = [
        "exécute", "exécuter", "calcule", "calculer", "génère", "générer",
        "script", "code", "programme", "python", "plot", "graphique",
        "visualise", "visualiser", "simule", "simuler"
    ]

    # Count keyword matches in question (each match = +1 point)
    analysis_score = sum(1 for kw in analysis_keywords if kw in question_lower)
    rag_score = sum(1 for kw in rag_keywords if kw in question_lower)
    code_score = sum(1 for kw in code_keywords if kw in question_lower)

    # CONFIDENCE CALCULATION: Based on keyword match strength
    # Strong match: 5+ keywords from leading category → confidence 0.95
    # Moderate match: 2-4 keywords → confidence 0.85
    # Weak match: 1 keyword (clear) → confidence 0.75
    # Marginal: 1 keyword but trailing > 0 → confidence 0.60
    def calculate_confidence(leading_score: int, trailing_score: int) -> float:
        if leading_score == 0:        # No keywords at all
            return CONFIDENCE_LOW     # 0.50 — triggers LLM fallback
        elif leading_score >= 5:      # Strong keyword presence
            return 0.95
        elif leading_score >= 2:      # Moderate presence (2-4 keywords) — was missing!
            return 0.85
        elif trailing_score == 0:     # Single keyword, no competition
            return 0.75
        else:                         # Single keyword but trailing has some hits
            return 0.60

    # Decision logic: if one category clearly leads, use that category
    scores = {"analysis": analysis_score, "rag": rag_score, "code": code_score}
    leading = max(scores, key=scores.get)

    # Check if leader has a clear lead (single unique maximum)
    if scores[leading] > 0 and list(scores.values()).count(scores[leading]) == 1:
        # One category has a clear lead
        task_type = leading
        # Get second-highest score for confidence calculation
        other_scores = [s for k, s in scores.items() if k != leading]
        trailing_score = max(other_scores) if other_scores else 0
        confidence_score = calculate_confidence(scores[leading], trailing_score)
        logger.debug(f"Keyword match: {task_type.upper()} ({scores[leading]} hits, conf={confidence_score:.2f})")
    else:
        # ═══════════════════════════════════════════════════════════════════════════════
        # STAGE 2 — LLM classification (when keywords ambiguous: tied or both zero)
        # ═══════════════════════════════════════════════════════════════════════════════
        # Call LLM for semantic analysis since keyword matching inconclusive
        logger.debug(f"Keywords ambiguous (analysis={analysis_score}, rag={rag_score}, code={code_score}) → using LLM")
        task_type = _llm_classify(question)
        confidence_score = CONFIDENCE_MEDIUM if any(s > 0 for s in scores.values()) else CONFIDENCE_LOW

    logger.info(f"Task classified: {task_type} (analysis={analysis_score}, rag={rag_score}, code={code_score}, conf={confidence_score:.2f})")

    return {
        **state,
        "language": language,
        "task_type": task_type,
        "confidence_score": confidence_score,  # NEW: Confidence metric
        "steps_taken": state.get("steps_taken", []) + [f"classify → {task_type} (conf={confidence_score:.2f})"]
    }


def _llm_classify(question: str) -> str:
    """
    HELPER: LLM-based classification for ambiguous questions.

    Called when keyword matching produces tied or zero scores.
    Uses semantic analysis via mistral-nemo to distinguish between:
    - 'analysis': Questions about analyzing data files, ML models, statistics
    - 'rag': Questions about document content, regulations, compliance

    Input:
        question (str): User's original question (French or English)

    Output:
        str: Either 'analysis' or 'rag'

    Performance:
    - LLM inference: ~1-2 seconds
    - Response parsing: ~10ms

    Error Handling:
    - LLM timeout/error defaults to 'rag' (safest default)
    """
    try:
        # Get LLM and build classification prompt
        llm = get_llm()
        prompt = f"""Classifie cette question en UN seul mot: 'analysis', 'code' ou 'rag'.
- 'analysis': questions sur des fichiers CSV, données, statistiques, ML
- 'code': questions sur l'exécution de code, programmation, scripts Python
- 'rag': questions sur des documents PDF, lois, réglementations, RGPD

Question: {question}

Réponds UNIQUEMENT avec 'analysis', 'code' ou 'rag'."""

        # Invoke LLM and extract response
        response = llm.invoke([HumanMessage(content=prompt)])
        result = response.content.strip().lower()

        # Parse LLM response (handles extra text, whitespace, etc.)
        if "analysis" in result:
            logger.debug(f"LLM classified as: analysis")
            return "analysis"
        elif "code" in result:
            logger.debug(f"LLM classified as: code")
            return "code"
        elif "rag" in result:
            logger.debug(f"LLM classified as: rag")
            return "rag"
        else:
            # Response didn't contain expected keyword, default to RAG
            logger.warning(f"LLM response unexpected: {result} — defaulting to rag")
            return "rag"  # RAG is safer default

    except Exception as e:
        # Any error (timeout, Ollama down, network) → default to RAG
        logger.warning(f"LLM classification failed: {e} — defaulting to rag")
        return "rag"


# ═══════════════════════════════════════════
# NODE 2a — Run analysis tool
# ═══════════════════════════════════════════

def run_analysis_node(state: AgentState) -> AgentState:
    """
    NODE 2a: Execute Phase 1 CSV analysis pipeline.

    Called when task_type == 'analysis'. Wraps analysis_tool.run_analysis() in graph node.
    Handles validation, tool execution, error recovery, and state mutation.

    Validation Checks:
    1. dataset_path must be provided
    2. If missing → return error state without invoking tool

    Execution Pipeline (4 stages):
    STAGE 1: Load & validate CSV
    STAGE 2: Exploratory Data Analysis
    STAGE 3: AutoML + SHAP (bottleneck: 70-80% of runtime)
    STAGE 4: Anomaly Detection

    Output State Changes:
    - result: Analysis results dict
    - answer: French narrative
    - error: str or None
    - steps_taken: Appended with 'analysis → success' or 'failed'

    Performance: 10-40 seconds typical
    """
    # PRE-FLIGHT: Check dataset path provided
    dataset_path = state.get("dataset_path")

    if not dataset_path:
        # Dataset path required for analysis, cannot proceed
        logger.warning("No dataset path provided for analysis task")
        return {
            **state,
            "answer": "Pour analyser des données, veuillez fournir le chemin vers un fichier CSV.",
            "error": "dataset_path manquant",
            "steps_taken": state.get("steps_taken", []) + ["analysis → no dataset"]
        }

    # EXECUTE: Call Phase 1 analysis tool (blocks 10-40 seconds)
    logger.info(f"Running analysis on: {dataset_path}")
    result = run_analysis(dataset_path)

    # RESULT HANDLING: Check tool success flag
    if not result["success"]:
        logger.error(f"Analysis tool failed: {result['error']}")
        return {
            **state,
            "answer": f"Erreur lors de l'analyse: {result['error']}",
            "error": result["error"],
            "steps_taken": state.get("steps_taken", []) + ["analysis → failed"]
        }

    # SUCCESS: Tool completed, return full results
    logger.info(f"Analysis succeeded: {result['rows']} rows, {result['columns']} columns")
    
    # STORE IN MEMORY: Save analysis for multi-turn follow-up questions
    session_id = state.get("session_id", "default")
    if result["success"]:
        _store_analysis_in_memory(session_id, result)
        logger.debug(f"Stored analysis in session {session_id} for multi-turn context")
    
    return {
        **state,
        "result": result,
        "answer": result["answer"],
        "error": None,
        "steps_taken": state.get("steps_taken", []) + ["analysis → success"]
    }


# ═══════════════════════════════════════════
# NODE 2b — Run RAG tool
# ═══════════════════════════════════════════

def run_rag_node(state: AgentState) -> AgentState:
    """
    NODE 2b: Execute Phase 2 RAG (semantic search + LLM) pipeline.

    Called when task_type == 'rag'. Wraps rag_tool.ask_document() in graph node.
    Handles document discovery, search execution, and error recovery.

    Execution Pipeline (5 stages):
    STAGE 1: Validate question
    STAGE 2: Embed question (50-100ms)
    STAGE 3: Semantic search in pgvector (10-50ms)
    STAGE 4: Build RAG prompt
    STAGE 5: Generate answer with LLM (5-30 seconds, bottleneck)

    Output State Changes:
    - result: RAG results with answer + sources
    - answer: French response with citations
    - error: str or None
    - steps_taken: Appended with 'rag → success' or 'failed'

    Performance: 5-35 seconds typical
    """
    # PRE-FLIGHT: Get user question and list available documents
    question = state["question"]
    logger.info(f"Running RAG for: {question[:80]}")

    # Document discovery: Show which documents available (informational)
    docs = get_indexed_documents()
    if docs:
        logger.info(f"Indexed documents: {docs}")
    else:
        logger.info("No documents indexed yet for RAG search")

    # EXECUTE: Call Phase 2 RAG tool (blocks 5-35 seconds)
    result = ask_document(question)

    # RESULT HANDLING: Check tool success flag
    if not result["success"]:
        logger.error(f"RAG tool failed: {result['error']}")
        return {
            **state,
            "answer": f"Erreur RAG: {result['error']}",
            "error": result["error"],
            "steps_taken": state.get("steps_taken", []) + ["rag → failed"]
        }

    # SUCCESS: Tool completed, return full results with sources
    logger.info(f"RAG succeeded: {len(result.get('sources', []))} sources found")
    return {
        **state,
        "result": result,
        "answer": result["answer"],
        "error": None,
        "steps_taken": state.get("steps_taken", []) + ["rag → success"]
    }


# ═══════════════════════════════════════════
# NODE 2c — Run code sandbox
# ═══════════════════════════════════════════

def run_code_node(state: AgentState) -> AgentState:
    """
    NODE 2c: Execute user question as Python code in isolated sandbox.

    Called when task_type == 'code'. Generates Python code from question,
    validates it, then runs in isolated Docker container with resource limits.

    Execution Pipeline (3 stages):
    STAGE 1: Generate Python code from question via LLM
    STAGE 2: Validate generated code (AST + RestrictedPython)
    STAGE 3: Execute in Docker sandbox with timeout + resource limits

    Output State Changes:
    - result: Sandbox execution result with output/errors
    - answer: Formatted execution output
    - error: str or None
    - steps_taken: Appended with 'code → success' or 'failed'

    Performance: 10-35 seconds typical (sandbox execution dominated)
    """
    from backend.engines.sandbox.sandbox_runner import run_in_sandbox
    from backend.engines.sandbox.result_formatter import format_result

    question = state["question"]
    logger.info(f"Running code sandbox for: {question[:80]}")

    # STAGE 1: Generate Python code from question
    try:
        llm = get_llm()
        prompt = f"""Génère uniquement du code Python pour répondre à cette demande.
Réponds UNIQUEMENT avec le code Python, sans explications, sans balises markdown.

Demande: {question}"""
        response = llm.invoke([HumanMessage(content=prompt)])
        generated_code = response.content.strip()
        # Strip markdown fences if LLM adds them
        if generated_code.startswith("```"):
            generated_code = "\n".join(generated_code.split("\n")[1:-1])
        logger.debug(f"Generated code ({len(generated_code)} chars)")
    except Exception as e:
        logger.error(f"Code generation failed: {e}")
        return {
            **state,
            "error": f"Code generation failed: {e}",
            "answer": f"Impossible de générer le code: {e}",
            "steps_taken": state.get("steps_taken", []) + ["code → generation failed"]
        }

    # STAGE 2 & 3: Run in sandbox (validates + executes)
    sandbox_result = run_in_sandbox(generated_code)
    formatted = format_result(sandbox_result)

    if not formatted.success:
        logger.warning(f"Sandbox execution failed: {formatted.error}")
        return {
            **state,
            "result": sandbox_result,
            "error": formatted.error,
            "answer": f"Erreur lors de l'exécution: {formatted.error}",
            "steps_taken": state.get("steps_taken", []) + ["code → failed"]
        }

    logger.info(f"Code execution succeeded")
    return {
        **state,
        "result": sandbox_result,
        "answer": formatted.to_agent_message(),
        "error": None,
        "steps_taken": state.get("steps_taken", []) + ["code → success"]
    }


# ═══════════════════════════════════════════
# NODE 3 — Format final answer
# ═══════════════════════════════════════════

def format_answer(state: AgentState) -> AgentState:
    """
    NODE 3: Format and enrich final answer with source citations.

    Post-processing node that runs after analysis or RAG execution.
    Adds source citations for RAG answers, deduplicates sources, and prepares final response.

    Processing Logic:
    For RAG answers: Extract sources, format as markdown, deduplicate by (source, page)
    For analysis answers: Pass through unchanged (already complete)

    Output State Changes:
    - answer: Enriched with source citations (RAG only)
    - steps_taken: Appended with 'format → done'

    Performance: <10ms (string manipulation only)
    """
    # Extract answer and metadata from state
    answer = state.get("answer", "")
    result = state.get("result", {})
    task_type = state.get("task_type", "unknown")
    language = state.get("language", "fr")

    # POST-PROCESS RAG ANSWERS: Add source citations
    if task_type == "rag" and result:
        # Extract sources list from tool result
        sources = result.get("sources", [])
        if sources:
            # Append citations section to answer (bilingual)
            if language == 'en':
                answer += "\n\n**Sources consulted:**"
            else:
                answer += "\n\n**Sources consultées :**"
            
            # Deduplicate by (source, page) pair using set tracking
            seen = set()
            for s in sources:
                # Create unique key for deduplication
                key = f"{s['source']} p.{s['page']}"
                if key not in seen:
                    # Format source citation with similarity score (bilingual)
                    if language == 'en':
                        answer += f"\n- {s['source']} (page {s['page']}, similarity: {s['similarity']:.2f})"
                    else:
                        answer += f"\n- {s['source']} (page {s['page']}, similarité: {s['similarity']:.2f})"
                    seen.add(key)

    logger.info(f"Answer formatted: {len(answer)} chars")

    return {
        **state,
        "answer": answer,
        "steps_taken": state.get("steps_taken", []) + ["format → done"]
    }


# ═══════════════════════════════════════════
# ROUTER — decides which node to run
# ═══════════════════════════════════════════

def route_task(state: AgentState) -> Literal["analysis", "rag", "code"]:
    """
    ROUTER: Conditional edge that directs execution.

    Called after classify_task. Routes to analysis, code, or RAG node based on task_type.
    RAG is default fallback since it requires no external file.

    Performance: <1ms (simple comparison)
    """
    # Conditional routing: analyze task_type to determine next node
    task_type = state.get("task_type", "rag")
    
    if task_type == "analysis":
        # Route to Phase 1 (CSV analysis pipeline)
        return "analysis"
    elif task_type == "code":
        # Route to Phase 3 (Code sandbox execution)
        return "code"
    
    # Default to Phase 2 (RAG) for safety (requires no external file)
    return "rag"


# ═══════════════════════════════════════════
# BUILD GRAPH
# ═══════════════════════════════════════════

def build_agent() -> StateGraph:
    """
    Build and compile the master LangGraph agent.

    Constructs the 4-node state machine with conditional routing:
    classify → (analysis | rag) → format → END

    Graph Structure:
    - StateGraph(AgentState): Typed edge with AgentState schema
    - Nodes: 4 nodes (classify, analysis, rag, format)
    - Edges: Sequential + conditional routing
    - Entry: classify, Exit: END

    Returns:
        CompiledStateGraph: Ready to invoke with .invoke(initial_state)

    Performance: Graph compilation <100ms
    """
    # Initialize LangGraph StateGraph with AgentState schema
    graph = StateGraph(AgentState)

    # NODES: Register all 4 processing nodes
    graph.add_node("classify", classify_task)  # Node 1: Task classification
    graph.add_node("analysis", run_analysis_node)  # Node 2a: Phase 1 analysis
    graph.add_node("rag", run_rag_node)  # Node 2b: Phase 2 RAG
    graph.add_node("code", run_code_node)  # Node 2c: Phase 3 code execution
    graph.add_node("format", format_answer)  # Node 3: Answer formatting

    # ENTRY POINT: Always start with classification
    graph.set_entry_point("classify")

    # CONDITIONAL ROUTING: From classify → analysis OR code OR rag
    graph.add_conditional_edges(
        "classify",  # From node
        route_task,  # Router function
        {
            "analysis": "analysis",  # If analysis task
            "code": "code",  # If code task
            "rag": "rag"  # If RAG task
        }
    )

    # SEQUENTIAL EDGES: All paths converge at format
    graph.add_edge("analysis", "format")
    graph.add_edge("code", "format")
    graph.add_edge("rag", "format")
    
    # EXIT: Format → END
    graph.add_edge("format", END)

    return graph.compile()


# ═══════════════════════════════════════════
# PUBLIC ENTRY POINT
# ═══════════════════════════════════════════

def run_agent(
    question: str,
    dataset_path: str = None,
    pdf_source: str = None,
    session_id: str = "default"
) -> dict:
    """
    PUBLIC ENTRY POINT: Run master agent on user question with session context.

    Main user-facing function that orchestrates entire conversation flow:
    1. Validate input
    2. Build graph
    3. Retrieve session memory for multi-turn context
    4. Execute graph workflow
    5. Return structured result with confidence score

    Input Parameters:
    - question (str, required): User's question in French or English
      Example: "Analysez ce fichier CSV", "Qu'est-ce que le RGPD?"
    - dataset_path (str, optional): File path to CSV for analysis tasks
      Example: "/data/sales.csv"
    - pdf_source (str, optional): PDF filter for RAG tasks (rarely used)
      Example: "regulations.pdf" (search only in this PDF)
    - session_id (str, optional): Conversation session identifier
      Example: "user_12345_2024-03-11"
      Default: "default" (no multi-turn memory)
      Usage: Group related questions for context-aware responses

    Pre-Execution Checks:
    - question: Must not be empty or whitespace-only
    - Returns error dict if validation fails
    - Retrieves prior analysis from session memory if available

    Graph Execution (sequential, blocking):
    - Builds graph fresh each call
    - Initializes AgentState with provided parameters and session context
    - Executes through all nodes: classify → analysis/rag → format
    - Blocks until completion (5-50 seconds typical)

    Return Value:
    dict with fields:
    - success (bool): True if agent completed without exception
    - question (str): Original user question
    - task_type (str): Detected task type ('analysis', 'rag')
    - confidence_score (float): Classification confidence (0.0-1.0)
      * 0.95: Very confident (strong keyword match)
      * 0.75-0.85: Confident (moderate keyword match)
      * 0.70: LLM classification (less certain)
      * 0.50: Ambiguous (triggers LLM fallback or error)
    - answer (str): Final French response to user
    - steps_taken (list): Execution trace for debugging
      Example: ['classify → analysis (conf=0.95)', 'analysis → success', 'format → done']
    - result (dict): Full tool output (analysis metrics or RAG sources)
    - session_memory (dict, optional): Prior analyses if multi-turn context available
    - error (str or None): Error message if success=False

    Error Handling Strategy:
    VALIDATION: Empty question → immediate return error dict (no graph execution)
    EXECUTION: Graph exception → caught, logged, return error dict
    STATE MUTATION: Graceful degradation (error in one node doesn't crash graph)
    CONFIDENCE: Returned even on error (classifies as best as possible)

    Multi-Turn Conversation Example:
    ```python
    # Turn 1: Analyze dataset
    r1 = run_agent(
        question="Analyse ce dataset",
        dataset_path="data/sales.csv",
        session_id="user_123"
    )
    # Result includes best_model, anomalies, features

    # Turn 2: Follow-up question (agent remembers Turn 1)
    r2 = run_agent(
        question="Quelles anomalies as-tu trouvé dans l'analyse précédente?",
        session_id="user_123"  # Same session ID
    )
    # Agent can reference prior analysis without re-running
    ```

    Performance:
    - Input validation: <1ms
    - Graph building: ~100ms
    - Session memory retrieval: <10ms
    - Execution: 5-50 seconds depending on task
    - Total: ~5-50 seconds

    Scalability Considerations:
    - Graph built fresh each call (optimization: cache + reset)
    - Supports sequential queries (not concurrent)
    - Session memory is in-memory (scales to ~1000 sessions)
    - For production: Migrate to persistent database (PostgreSQL)
    """
    # VALIDATION: Check question not empty
    if not question or not question.strip():
        return {
            "success": False,
            "error": "Question vide",
            "confidence_score": 0.0
        }

    # LOG: Agent invocation (first 80 chars)
    logger.info(f"Agent invoked (session={session_id}): {question[:80]}")

    # BUILD: Construct LangGraph
    agent = build_agent()

    # MEMORY: Retrieve prior analyses for multi-turn context
    session_memory = _get_session_memory(session_id)
    prior_context = session_memory["last_analysis"] if session_memory["last_analysis"] else None

    # INIT: Create initial graph state with all fields
    initial_state = {
        "messages": [HumanMessage(content=question)],  # LangGraph message accumulation
        "question": question,  # User's query
        "session_id": session_id,  # NEW: Session identifier for memory
        "task_type": None,  # Will be set by classify_task node
        "confidence_score": 0.0,  # NEW: Confidence metric (set by classify_task)
        "dataset_path": dataset_path,  # Optional CSV path (for analysis)
        "pdf_source": pdf_source,  # Optional PDF filter (for RAG)
        "result": None,  # Tool output (will be set by analysis/rag node)
        "answer": None,  # Generated answer (will be set by tool)
        "error": None,  # Error message if any step fails
        "steps_taken": [],  # Execution trace for debugging
        "prior_analysis_context": prior_context  # NEW: Multi-turn memory reference
    }

    try:
        # EXECUTE: Run graph through all nodes (blocks until complete)
        # Typical time: 5-50 seconds depending on task complexity
        final_state = agent.invoke(initial_state)

        # SUCCESS: Extract results from final state for user
        logger.info(f"Agent completed (session={session_id}): {final_state.get('task_type')} task")
        
        result_dict = {
            "success": True,
            "question": question,
            "task_type": final_state.get("task_type"),  # 'analysis' or 'rag'
            "confidence_score": final_state.get("confidence_score", 0.0),  # NEW: Classification confidence
            "answer": final_state.get("answer"),  # French response
            "steps_taken": final_state.get("steps_taken", []),  # Execution trace
            "result": final_state.get("result"),  # Full tool metadata
            "error": final_state.get("error")  # None if successful
        }
        
        # Add session memory reference if available
        if prior_context:
            result_dict["session_memory"] = {
                "prior_analysis": prior_context,
                "all_analyses_count": len(session_memory["analyses"])
            }
        
        return result_dict

    except Exception as e:
        # EXCEPTION HANDLING: Catch any uncaught errors from graph nodes
        logger.error(f"Agent failed with exception (session={session_id}): {e}")
        return {
            "success": False,
            "question": question,
            "confidence_score": 0.0,  # NEW: Include confidence even on error
            "error": str(e)  # Return exception message to caller
        }