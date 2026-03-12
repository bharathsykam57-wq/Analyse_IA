"""agent_state.py — Agent conversation state management for Analyse_IA Master Agent

Defines the LangGraph state schema that flows between agent nodes during conversation.

Architecture Overview:
- Central state repository: Passed through all agent nodes during execution
- Multi-mode agent: Routes between RAG (vector search) and Analysis (AutoML/EDA)
- Conversation history: LangGraph manages message accumulation automatically
- Task routing: Classifier node determines analysis vs. RAG based on question
- Status tracking: Captures intermediate results and error states

State Lifecycle:
1. Initialize: User question + empty results + fallback to 'unknown' task
2. Classify: Router node sets task_type ('analysis', 'rag', or 'unknown')
3. Execute: Relevant tool node (RAG or Analysis) processes and fills result
4. Generate: Answer generation node creates French response from result
5. Return: Final answer delivered to user with optional error context

Integration Points:
- RAG pipeline: Accepts pdf_source, stores search results and LLM answer
- Analysis engine: Accepts dataset_path, stores AutoML/EDA results
- LangGraph framework: Messages field managed by add_messages reducer
- Error handling: Captures failures without stopping execution (graceful degradation)

Usage Example:
    state = AgentState(
        messages=[...],  # Managed by LangGraph
        question="Analyze this dataset or answer this question?",
        task_type=None,  # Set by classifier
        dataset_path="data/sample.csv",  # Optional, for analysis
        pdf_source=None,  # Optional, for RAG
        result={},  # Filled by execution node
        answer=None,  # Filled by generation node
        error=None,  # Set only if problem occurs
        steps_taken=["classify", "execute_analysis"]  # Track execution path
    )

Performance Considerations:
- messages field growth: Accumulates indefinitely (consider pruning for long conversations)
- result dict size: Limited by tool output (typically <100KB)
- State serialization: TypedDict optimized for JSON serialization in LangGraph
"""

from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Conversation state passed between all LangGraph nodes in agent execution.

    Serves as the central state object flowing through the agent graph:
    - Each node reads relevant fields and updates state before returning
    - LangGraph manages consistency and message accumulation
    - Supports both RAG and Analysis workflows simultaneously
    - Enables multi-turn conversations with persistent context

    Field Descriptions:

    messages (Annotated[list, add_messages]):
        Full conversation history with sender/type information.
        - Type: List of BaseMessage objects (LangGraph managed)
        - Accumulation: add_messages reducer prevents duplicates, maintains order
        - Updated by: All nodes that generate responses
        - Usage: Input to LLM for context-aware generation
        - Example: [HumanMessage("question?"), AIMessage("answer..."), ...]
        - Notes: Grows linearly; consider archiving for 100+ message conversations

    question (str):
        Current user question triggering agent execution.
        - Type: String in French or English (normalized to French internally)
        - Set by: Initial node from user input
        - Length: Typically 10-500 characters
        - Constraints: Required (never None) to trigger agent
        - Example: "Quelles anomalies détectez-vous dans ce fichier?"
        - Processing: Passed to classifier for task_type determination

    task_type (Optional[str]):
        Detected task category for routing to appropriate tool.
        - Possible values: 'analysis' (CSV/data), 'code' (code execution), 'rag' (PDF documents), 'unknown'
        - Set by: Classifier node based on question content
        - Default: None initially, set before execution
        - Routing: Determines which tool node executes (Analysis vs. Code vs. RAG)
        - Fallback: If 'unknown', return helpful message without execution
        - Example conditions:
          - 'analysis': Question mentions "dataset", "analyze", "detect", "column"
          - 'code': Question mentions "execute", "script", "generate", "plot", "calculate"
          - 'rag': Question mentions "CNIL", "regulation", "compliance", "document"
          - 'unknown': Unclear intent or ambiguous request

    dataset_path (Optional[str]):
        Path to CSV file for analysis tasks (unused for RAG).
        - Type: Absolute or relative file path
        - Set by: Classifier node or user input parsing
        - Example: "data/processed/anomalies_2025.csv" or "/data/raw/sensor.csv"
        - Validation: Checked by analysis node (must exist)
        - Processing: Passed to AutoML/EDA pipeline if task_type='analysis'
        - Default: None (indicates RAG task or no dataset specified)
        - Error handling: If file not found, sets error field

    pdf_source (Optional[str]):
        Source document identifier for RAG tasks (unused for Analysis).
        - Type: Document name or identifier in vector database
        - Set by: Classifier node or extracted from question
        - Example: "cnil_ia_guidelines.pdf" or "CNIL_2024_AI_Regulations"
        - Validation: Checked by RAG node (must exist in pgvector)
        - Processing: Passed to search_similar() and ask() RAG functions
        - Default: None (indicates Analysis task or generic RAG on all documents)
        - Error handling: If document not indexed, sets error field

    result (Optional[dict]):
        Intermediate structured result from executed tool (Analysis or RAG).
        - Type: Dictionary with tool-specific structure
        - Set by: Execution node (Analysis or RAG)
        - Analysis result format: {anomalies: [...], stats: {...}, model_info: {...}}
        - RAG result format: {answer: "...", sources: [...], success: bool}
        - Size: Typically <100KB (tool output limited)
        - Processing: Consumed by answer generation node to create final response
        - Default: None initially, filled during execution phase
        - Validation: Checked for 'success' flag before answer generation

    answer (Optional[str]):
        Final French response generated from result (delivered to user).
        - Type: String in French language
        - Set by: Answer generation node
        - Length: Typically 100-2000 characters
        - Example: "Le système a détecté 3 anomalies dans le jeu de données..."
        - Content: Combines result data + source attribution + explanations
        - Language: French for compliance and user base (CNIL context)
        - Processing: Returned to user or appended to messages for feedback
        - Default: None initially, set in final generation step
        - Fallback: If execution fails, contains error summary instead

    error (Optional[str]):
        Error message captured during execution (permits graceful degradation).
        - Type: String (human-readable error description)
        - Set by: Any node encountering exception
        - Trigger: File not found, database connection error, API timeout, validation
        - Example: "CSV file not found: data/sample.csv" or "RAG search returned 0 results"
        - Handling: If set, answer node generates explanation for user instead of failing
        - Default: None (no error)
        - Usage: Prevents silent failures, enables debugging and user feedback

    steps_taken (list[str]):
        Execution trace logging which nodes processed the state.
        - Type: List of step name strings
        - Set by: Each node appends its name before processing
        - Example: ["classify", "execute_analysis", "generate_answer"]
        - Order: Chronological (represents execution path taken)
        - Purpose: Debugging (verify correct nodes ran), logging (trace execution)
        - Analysis path typical: ["classify", "execute_analysis", "generate_answer"]
        - RAG path typical: ["classify", "execute_rag", "generate_answer"]
        - Fallback path: ["classify", "generate_answer"] (if task_type='unknown')
        - Performance implications: Minimal (list append operation <1μs per step)

    session_id (Optional[str]):
        Unique identifier for conversation session (multi-turn support).
        - Type: String identifier for grouping related questions
        - Set by: User input or generated from timestamp + user_id
        - Example: "user_12345_2024-03-11" or "session_abc123"
        - Purpose: Group questions in same conversation thread
        - Usage: Retrieve prior analysis results for context-aware follow-ups
        - Default: "default" (no session tracking, each question independent)
        - Multi-turn example:
          * Q1 with session_id="user_123" → stores analysis result in memory
          * Q2 with session_id="user_123" → retrieves and references Q1 result
        - Persistence: In-memory storage per session_id (clears on server restart)

    confidence_score (Optional[float]):
        Classification confidence metric (0.0-1.0) from hybrid keyword+LLM approach.
        - Type: Float between 0.0 (not confident) and 1.0 (very confident)
        - Set by: Classifier node based on keyword matching strength + LLM fallback
        - Calculation formula:
          * 0.95: Strong keyword match (5+ keywords from leading category)
          * 0.85: Moderate keyword match (3-4 keywords)
          * 0.75: Single keyword match with no ambiguity
          * 0.70: LLM semantic classification (triggered by tied/zero keyword scores)
          * 0.50: Ambiguous classification or error condition
        - Usage: Explainability (show users how certain agent is about task type)
        - Example output: {"task_type": "analysis", "confidence_score": 0.95}
        - Interpretation:
          * ≥0.90: High confidence, use classification without hesitation
          * 0.70-0.85: Moderate confidence, classification likely correct but consider alternatives
          * <0.70: Low confidence, classification may be uncertain, consider user clarification
        - Default: 0.0 initially, set by classify_task node

    prior_analysis_context (Optional[dict]):
        Reference to most recent analysis result from same session (multi-turn memory).
        - Type: Dictionary with analysis metadata or None if no prior analysis
        - Set by: run_agent() function by retrieving from SESSION_MEMORY
        - Structure: {"dataset_path": "...", "rows": int, "best_model": "...", "anomalies": {...}}
        - Usage: Enable follow-up questions to reference prior analysis
        - Example follow-up: Q1: "Analyze data.csv" → Q2: "Refine the anomaly detection"
        - Access: Question classification node can use this for context
        - Default: None (no prior analysis in session)
        - Lifecycle: Only populated if same session_id used for multiple questions
        - Privacy: Session-scoped, not shared across users or sessions

    """
    # Core message management (LangGraph accumulation)
    messages:                 Annotated[list, add_messages]
    
    # User input and intent
    question:                 str
    language:                 str                          # 'fr' or 'en'
    
    # Task routing fields
    task_type:                Optional[str]
    dataset_path:             Optional[str]
    pdf_source:               Optional[str]
    
    # Execution results and responses
    result:                   Optional[dict]
    answer:                   Optional[str]
    error:                    Optional[str]
    
    # Execution tracking
    steps_taken:              list[str]
    
    # Multi-turn support (NEW)
    session_id:               Optional[str]                # Session identifier for multi-turn conversations
    confidence_score:         Optional[float]              # Classification confidence (0.0-1.0)
    prior_analysis_context:   Optional[dict]               # Reference to previous analysis in same session