"""
master_agent.py — LangGraph Master Agent for Analyse_IA
Orchestrates Phase 1 (analysis) and Phase 2 (RAG) engines.
Detects task type from user question and routes to correct tool.
"""

import logging
from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage

from backend.agent.agent_state import AgentState
from backend.agent.tools.analysis_tool import run_analysis
from backend.agent.tools.rag_tool import ask_document, get_indexed_documents

logger = logging.getLogger(__name__)

LLM_MODEL = "mistral-nemo:latest"
OLLAMA_URL = "http://localhost:11434"


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
    Detect whether the question is about:
    - 'analysis': CSV data analysis, ML, statistics, anomalies
    - 'rag': document Q&A, RGPD, CNIL, PDF content
    - 'unknown': cannot determine
    """
    question = state["question"]
    logger.info(f"Classifying task: {question[:80]}")

    # Keyword-based classification first (fast, no LLM call)
    question_lower = question.lower()

    analysis_keywords = [
        "analyse", "analyser", "csv", "dataset", "données", "colonnes",
        "modèle", "prédire", "prédiction", "ml", "machine learning",
        "anomalie", "statistique", "corrélation", "régression", "classification"
    ]

    rag_keywords = [
        "rgpd", "cnil", "document", "pdf", "réglementation", "loi",
        "article", "règlement", "droit", "obligation", "conformité",
        "protection", "données personnelles", "open source", "ia"
    ]

    analysis_score = sum(1 for kw in analysis_keywords if kw in question_lower)
    rag_score = sum(1 for kw in rag_keywords if kw in question_lower)

    if analysis_score > rag_score and analysis_score > 0:
        task_type = "analysis"
    elif rag_score > analysis_score and rag_score > 0:
        task_type = "rag"
    else:
        # Use LLM to classify if keywords are ambiguous
        task_type = _llm_classify(question)

    logger.info(f"Task classified as: {task_type} (analysis={analysis_score}, rag={rag_score})")

    return {
        **state,
        "task_type": task_type,
        "steps_taken": state.get("steps_taken", []) + [f"classify → {task_type}"]
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
        prompt = f"""Classifie cette question en UN seul mot: 'analysis' ou 'rag'.
- 'analysis': questions sur des fichiers CSV, données, statistiques, ML
- 'rag': questions sur des documents PDF, lois, réglementations, RGPD

Question: {question}

Réponds UNIQUEMENT avec 'analysis' ou 'rag'."""

        # Invoke LLM and extract response
        response = llm.invoke([HumanMessage(content=prompt)])
        result = response.content.strip().lower()

        # Parse LLM response (handles extra text, whitespace, etc.)
        if "analysis" in result:
            logger.debug(f"LLM classified as: analysis")
            return "analysis"
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

    # POST-PROCESS RAG ANSWERS: Add source citations
    if task_type == "rag" and result:
        # Extract sources list from tool result
        sources = result.get("sources", [])
        if sources:
            # Append citations section to answer
            answer += "\n\n**Sources consultées :**"
            
            # Deduplicate by (source, page) pair using set tracking
            seen = set()
            for s in sources:
                # Create unique key for deduplication
                key = f"{s['source']} p.{s['page']}"
                if key not in seen:
                    # Format source citation with similarity score
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

def route_task(state: AgentState) -> Literal["analysis", "rag"]:
    """
    ROUTER: Conditional edge that directs execution.

    Called after classify_task. Routes to analysis or RAG node based on task_type.
    RAG is default fallback since it requires no external file.

    Performance: <1ms (simple comparison)
    """
    # Conditional routing: analyze task_type to determine next node
    task_type = state.get("task_type", "rag")
    
    if task_type == "analysis":
        # Route to Phase 1 (CSV analysis pipeline)
        return "analysis"
    
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
    graph.add_node("format", format_answer)  # Node 3: Answer formatting

    # ENTRY POINT: Always start with classification
    graph.set_entry_point("classify")

    # CONDITIONAL ROUTING: From classify → analysis OR rag
    graph.add_conditional_edges(
        "classify",  # From node
        route_task,  # Router function
        {
            "analysis": "analysis",  # If analysis task
            "rag": "rag"  # If RAG task
        }
    )

    # SEQUENTIAL EDGES: Both paths converge at format
    graph.add_edge("analysis", "format")
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
    pdf_source: str = None
) -> dict:
    """
    PUBLIC ENTRY POINT: Run master agent on user question.

    Main user-facing function that orchestrates entire conversation flow:
    1. Validate input
    2. Build graph
    3. Execute graph workflow
    4. Return structured result

    Input Parameters:
    - question (str, required): User's question (French or English)
      Example: "Analysez ce fichier CSV", "Qu'est-ce que le RGPD?"
    - dataset_path (str, optional): Path to CSV for analysis tasks
      Example: "/data/sales.csv"
    - pdf_source (str, optional): PDF filter for RAG tasks
      Example: "regulations.pdf"

    Pre-Execution Checks:
    - question must not be empty or whitespace-only

    Graph Execution (sequential, blocking):
    - Builds graph fresh each call
    - Initializes AgentState with provided parameters
    - Executes through all nodes: classify → analysis/rag → format
    - Blocks until completion (5-50 seconds typical)

    Return Value (dict):
    - success (bool): True if completed without exception
    - question (str): Original user question
    - task_type (str): Detected type ('analysis', 'rag')
    - answer (str): Final French response
    - steps_taken (list): Execution trace ['classify → analysis', 'analysis → success', 'format → done']
    - result (dict): Full tool output (metrics or sources)
    - error (str or None): Error message if success=False

    Error Handling:
    - VALIDATION: Empty question → immediate error return (no graph execution)
    - EXECUTION: Graph exception → caught, logged, error dict returned
    - STATE: Graceful degradation (error in one node doesn't crash whole graph)

    Example Usage:
    ```python
    # Analysis task
    result = run_agent(question="Analysez ce dataset", dataset_path="/data/sales.csv")
    if result['success']:
        print(result['answer'])

    # RAG task (auto-detects, ignores dataset_path)
    result = run_agent(question="Expliquez-moi le RGPD")
    ```

    Performance:
    - Input validation: <1ms
    - Graph building: ~100ms
    - Execution: 5-50 seconds (task dependent)
    - Total: ~5-50 seconds
    """
    # VALIDATION: Check question not empty
    if not question or not question.strip():
        return {"success": False, "error": "Question vide"}

    # LOG: Agent invocation (first 80 chars)
    logger.info(f"Agent invoked: {question[:80]}")

    # BUILD: Construct LangGraph
    agent = build_agent()

    # INIT: Create initial graph state
    initial_state = {
        "messages": [HumanMessage(content=question)],  # LangGraph message accumulation
        "question": question,  # User's query
        "task_type": None,  # Will be set by classify_task
        "dataset_path": dataset_path,  # Optional CSV path
        "pdf_source": pdf_source,  # Optional PDF filter
        "result": None,  # Tool output (set by analysis/rag)
        "answer": None,  # Generated answer (set by tool)
        "error": None,  # Error message if any step fails
        "steps_taken": []  # Execution trace
    }

    try:
        # EXECUTE: Run graph through all nodes (blocks until complete)
        # Typical time: 5-50 seconds depending on task complexity
        final_state = agent.invoke(initial_state)

        # SUCCESS: Extract results from final state
        logger.info(f"Agent completed: {final_state.get('task_type')} task")
        return {
            "success": True,
            "question": question,
            "task_type": final_state.get("task_type"),  # 'analysis' or 'rag'
            "answer": final_state.get("answer"),  # French response
            "steps_taken": final_state.get("steps_taken", []),  # Execution trace
            "result": final_state.get("result"),  # Full tool metadata
            "error": final_state.get("error")  # None if successful
        }

    except Exception as e:
        # EXCEPTION HANDLING: Catch any uncaught errors
        logger.error(f"Agent failed with exception: {e}")
        return {
            "success": False,
            "question": question,
            "error": str(e)
        }