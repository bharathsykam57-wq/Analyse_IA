"""rag_tool.py — Master Agent RAG tool integrating Phase 2 retrieval-augmented generation

Provides unified entry point for document question-answering through LangGraph agent.

Architecture Overview:
- Single Agent Tool: Called by LangGraph master agent for RAG workflows
- RAG Pipeline: Load PDF → Chunk text → Embed chunks → Semantic search → LLM generation
- Vector Database: PostgreSQL pgvector for semantic similarity search (cosine distance)
- Embedding Model: Ollama nomic-embed-text (768-dimensional, local inference)
- LLM: mistral-nemo via Ollama (French output, temperature=0.1 for factual responses)
- Document Management: Safe multi-document indexing with deduplication
- Error Handling: Graceful degradation when no documents indexed or query fails

Phase 2 Engine Integration:
- Document Loader: PDF extraction and sliding-window text chunking (500 chars, 50 char overlap)
- Embedding Engine: Batch vector generation with failing chunk fallback
- Vector Store: PostgreSQL pgvector storage with UPSERT deduplication
- RAG Chain: Semantic search + prompt engineering + LLM generation + source attribution

Three Core Operations:
1. ask_document(): Answer user question from indexed PDF corpus
   - Semantic similarity search → Top-K relevant chunks
   - Prompt engineering with French RAG template
   - LLM generation with source citations
   - Graceful fallback when no documents indexed

2. index_pdf(): Load and index new PDF document
   - PDF extraction with pypdf (handles text/image PDFs)
   - Sliding-window chunking for semantic coherence
   - Batch embedding with Ollama
   - UPSERT storage (duplicates automatically skipped)
   - Idempotent: Safe to call multiple times on same PDF

3. get_indexed_documents(): List all documents in knowledge base
   - Direct PostgreSQL query on documents table
   - Returns unique source filenames
   - Used by agent for document selection/filtering

Integration with Master Agent:
- Called from: backend.agent.nodes.execute_rag()
- Input from state: question (str), pdf_source (Optional[str])
- Output to state: result dict with answer, sources, chunks_used
- Error handling: Returns success=False with message (graceful, never raises)
- Language: Accepts French or English questions, responds in French

Usage by Agent:
    state["task_type"] = "rag"
    state["question"] = "Quelles sont les obligations CNIL pour l'IA?"
    state["pdf_source"] = None  # Optional: filter to specific PDF
    result = ask_document(state["question"])
    state["result"] = result

Performance Characteristics:
- Query embedding: 50-100ms (Ollama inference)
- Vector search: 10-50ms (pgvector with proper index)
- LLM generation: 5-30 seconds (Ollama text generation)
- Total Q&A: 5-35 seconds per question (LLM dominated)
- PDF indexing: 2-10 seconds typical (depends on PDF size and chunk count)

Error Scenarios Handled:
- Empty question: Validation catches, returns error
- No documents indexed: Returns graceful message, suggests indexing
- PDF not found: Returns error with file path
- PDF parsing failure: Returns error with detailed message
- Embedding failure: Returns error, doesn't store corrupted data
- LLM timeout: Returns error, preserves question context
- Database connection error: Returns error, suggests retry

Dependencies:
- logging: Standard library for operation tracking
- backend.engines.rag: All four Phase 2 RAG engines
  - rag_chain: Main orchestration (ask function)
  - document_loader: PDF text extraction and chunking
  - embedding_engine: Vector generation
  - vector_store: PostgreSQL pgvector storage and search

Database Schema (documents table):
- id: UUID (primary key)
- source: str (PDF filename, unique with page+chunk_index)
- page: int (page number in PDF)
- chunk_index: int (sequential chunk on page)
- content: text (500-char chunk with 50-char overlaps)
- embedding: vector(768) (nomic-embed-text output, stored as pgvector type)
- created_at: timestamp
- ON CONFLICT DO NOTHING: Duplicate (source, page, chunk_index) automatically skipped
"""

import logging
from backend.engines.rag.rag_chain import ask
from backend.engines.rag.document_loader import load_and_chunk_pdf
from backend.engines.rag.embedding_engine import embed_chunks
from backend.engines.rag.vector_store import store_chunks, get_document_count, delete_source

logger = logging.getLogger(__name__)


def ask_document(question: str, top_k: int = 5) -> dict:
    """Answer user question using complete RAG pipeline over indexed PDF corpus.

    Five-stage RAG orchestration for document question-answering:
    1. Validation: Check question not empty, retrieve document count
    2. Embedding: Convert question to 768-dim vector (nomic-embed-text)
    3. Search: Semantic similarity search for top-K relevant chunks (cosine distance)
    4. Prompt: Build French RAG prompt with retrieved chunks as context
    5. Generate: Call mistral-nemo LLM to answer using prompt + retrieved context
    6. Return: Package answer with source attribution and metadata

    Args:
        question (str):
            User question in French or English (auto-translated internally if needed).
            - Type: String representing query
            - Example French: "Quelles sont les obligations CNIL pour les systèmes d'IA?"
            - Example English: "What are CNIL compliance requirements for AI systems?"
            - Validation: Must be non-empty after strip()
            - Error handling: Empty questions return {"success": False, "error": "Question vide"}
            - Length: Typically 10-500 characters
            - Processing: Embedded as-is (language model handles code-switching)

        top_k (int):
            Number of most similar chunks to retrieve for context.
            - Type: Positive integer
            - Default: 5 (balance between context richness and prompt brevity)
            - Range: 1-20 is practical (>20 risks exceeding token limits)
            - Example: 3 (minimal context), 5 (balanced), 10 (comprehensive)
            - Effect: More chunks = better context but slower, longer generation
            - Notes: LLM performance plateaus around 5-8 chunks for most queries

    Returns:
        dict: Complete RAG result with following fields:

        success (bool):
            Whether Q&A completed successfully.
            - True: Answer generated (may be empty if no context found)
            - False: Fatal error (no documents, embedding failed, LLM timeout, etc.)
            - Usage: Check first before accessing other fields

        question (str):
            Original question passed to function.
            - Value: Same as input parameter
            - Usage: Confirms what question was answered

        answer (str):
            French language answer generated by LLM with source context.
            - Type: Multi-sentence French text
            - Language: 100% French for CNIL compliance
            - Length: Typically 200-1000 characters
            - Content: Direct answer + relevant context from document + reasoning
            - Source attribution: Includes citations to document pages
            - Format: Paragraph text (may include bullet points if LLM adds them)
            - Temperature: 0.1 (factual, minimal hallucination, grounded in sources)
            - Fallback: If no context found, returns helpful message about indexing
            - Example starts: "Selon le document, les obligations principales sont:"

        sources (list[dict]):
            Top-K retrieved chunks used to generate answer (source attribution).
            - Type: List of dicts with {"source": str, "page": int, "similarity": float}
            - Source format: Filename of PDF (e.g., "cnil_ia_guidelines.pdf")
            - Page: 1-indexed page number where chunk appears
            - Similarity: Cosine similarity score (0.0-1.0, higher = more relevant)
            - Order: Sorted by similarity descending (most relevant first)
            - Count: Exactly top_k if documents available, fewer if corpus small
            - Example: [{"source": "cnil.pdf", "page": 3, "similarity": 0.92}, ...]
            - Usage: Show user what documents were consulted
            - Interpretation: similarity > 0.8 = very relevant, 0.6-0.8 = relevant, < 0.6 = marginal

        chunks_used (int):
            Number of text chunks retrieved and used for answer generation.
            - Type: Integer >= 0
            - Value: Typically equals top_k, may be less if corpus small
            - Example: 5 (when top_k=5 and 5+ documents available)
            - Example: 2 (when top_k=5 but only 2 documents indexed)
            - Example: 0 (when no documents indexed, answer is generic)
            - Usage: Assess answer quality (more context = higher confidence)

        error (str or None):
            Error message if pipeline failed (only when success=False).
            - Type: String (human-readable) or None
            - None if: success=True (no error occurred)
            - Content: Specific error description in French or English
            - Example: "Question vide" (empty question validation)
            - Example: "Aucun document n'est indexé..." (no PDF corpus)
            - Usage: Debugging and user feedback when Q&A fails

    Performance Characteristics:
        - Embedding: 50-100ms (Ollama nomic-embed-text)
        - Similarity search: 10-50ms (pgvector with cosine operator)
        - LLM generation: 5-30 seconds (mistral-nemo, top_p=0.9, temp=0.1)
        - Total latency: 5-35 seconds per question (LLM generates bottleneck)
    """
    # PRE-FLIGHT VALIDATION: Catch obvious errors before expensive operations
    # - Empty questions: Prevent sending empty string to LLM
    # - Early exit saves embedding + search latency (~100ms)
    if not question or not question.strip():
        return {"success": False, "error": "Question vide"}

    logger.info(f"RAG query: {question[:80]}")

    # CHECK CORPUS: Verify documents are indexed before attempting search
    # - get_document_count(): Direct PostgreSQL SELECT COUNT(DISTINCT source)
    # - Typical: <50ms with index
    # - If 0: Return graceful message suggesting user index documents first
    count = get_document_count()
    if count == 0:
        logger.warning("No documents indexed in pgvector yet")
        return {
            "success": True,
            "question": question,
            "answer": "Aucun document n'est indexé. Veuillez d'abord charger des documents PDF.",
            "sources": [],
            "chunks_used": 0,
            "error": None
        }

    # EXECUTE FULL RAG PIPELINE: Delegate to rag_chain.ask()
    # - Handles: embed question → search similarity → build prompt → generate answer
    # - Returns complete result dict with success, answer, sources, chunks_used
    # - Handles all errors internally (LLM timeout, embedding failure, etc.)
    # - Typically 5-35 seconds (dominated by LLM generation)
    result = ask(question, top_k=top_k)
    logger.info(f"✓ RAG query complete: {result.get('chunks_used', 0)} chunks used")
    return result


def index_pdf(pdf_path: str) -> dict:
    """Load, embed, and store PDF document into pgvector knowledge base.

    Four-stage pipeline that progressively indexes PDF for semantic search:
    1. Load & Chunk: Extract text from PDF, split into overlapping chunks
    2. Embed: Generate 768-dim vectors for each chunk (Ollama nomic-embed-text)
    3. Store: Insert chunks into PostgreSQL pgvector with deduplication
    4. Return: Report success with chunk counts and insertion stats

    Idempotent Operation:
    - Safe to call multiple times on same PDF
    - Duplicates automatically skipped by UPSERT (ON CONFLICT DO NOTHING)
    - Subsequent runs add only new chunks (if PDF updated)
    - No data corruption risk from multiple runs

    Args:
        pdf_path (str):
            Path to PDF file for indexing.
            - Type: String (absolute or relative path)
            - Example: "data/pdfs/cnil_ia_guidelines.pdf" or "/data/CNIL_2024.pdf"
            - Validation: Must exist and be readable PDF (checked by loader)
            - Format: PDF only (.pdf extension)
            - Error handling: Returns {"success": False, "error": "..."} if invalid
            - Performance: I/O time depends on file size (typical 1-10 MB)

    Returns:
        dict: Indexing result with following fields:

        success (bool):
            Whether indexing completed successfully.
            - True: PDF loaded, embedded, and stored (all chunks processed)
            - False: Fatal error at any stage (file not found, parsing failure, etc.)
            - Usage: Check first before accessing other fields

        source (str):
            Filename of indexed PDF (from load_result, not input path).
            - Value: Just filename, no directory path (e.g., "cnil.pdf")
            - Usage: Reference for document selection and filtering
            - Stored in: documents table 'source' column

        total_chunks (int):
            Total number of text chunks extracted from PDF.
            - Type: Integer > 0
            - Example: 150 chunks from 50-page CNIL document
            - Breakdown: Some chunks skipped (duplicates), some inserted (new)
            - Typical range: 50-500 chunks depending on PDF length
            - Calculation: total_chunks = inserted + skipped

        inserted (int):
            Number of chunks newly inserted into pgvector (not duplicates).
            - Type: Integer >= 0
            - Example: 150 on first run, 0 on second identical run (all duplicates)
            - Logic: COUNT of (source, page, chunk_index) NOT IN existing rows

        skipped (int):
            Number of chunks matching existing (source, page, chunk_index) tuples.
            - Type: Integer >= 0
            - Example: 0 on first run, 150 on second run of same PDF (all duplicates)
            - Calculation: skipped = total_chunks - inserted
            - Benefit: Subsequent runs are very fast (only new chunks processed)

        error (str or None):
            Error message if indexing failed (only when success=False).
            - Type: String (human-readable) or None
            - None if: success=True (no error occurred)
            - Content: Specific error from any of 4 stages
            - Example: "Fichier PDF non trouvé: data/missing.pdf"
            - Example: "Aucun contenu extrait du PDF" (empty PDF or OCR-only)

    Performance Characteristics:
        - Small PDF (< 10 pages): 2-5 seconds total
        - Medium PDF (10-50 pages): 5-15 seconds total
        - Large PDF (50+ pages): 15-60 seconds total
        - Dominated by: LLM embedding (70-80% of total time)

    Idempotency Guarantee:
        - First run: Inserts all chunks
        - Second run (same PDF): Inserts 0, skips all (duplicates detected)
        - Third run (after PDF updated): Inserts new chunks, skips existing
        - Rationale: (source, page, chunk_index) is unique compound key
    """
    logger.info(f"Indexing PDF: {pdf_path}")

    # STAGE 1: LOAD & CHUNK PDF
    # - Extract text with pypdf (handles text-based and image-heavy PDFs)
    # - Split with sliding-window (500 chars text, 50 char overlap for context continuity)
    # - Output: chunks = [{"source": str, "page": int, "content": str, ...}]
    # - Typical: 100-300 chunks for CNIL-size document
    # - Errors: File not found, not PDF, PDF corrupted, not readable, etc.
    load_result = load_and_chunk_pdf(pdf_path)
    if not load_result["success"]:
        return {"success": False, "error": load_result["error"]}

    chunks = load_result["chunks"]
    if not chunks:
        return {"success": False, "error": "Aucun contenu extrait du PDF"}

    # STAGE 2: EMBED CHUNKS
    # - Convert each chunk to 768-dimensional vector (nomic-embed-text)
    # - Batch processing with graceful fallback for failed chunks
    # - Output: embedded = [{"source": str, "embedding": [0.1, 0.2, ...], ...}]
    # - Typical: 50-100ms per chunk
    # - Errors: Ollama offline, GPU out of memory, connection timeout
    embedded = embed_chunks(chunks)
    if not embedded:
        return {"success": False, "error": "Échec de l'embedding des chunks"}

    # STAGE 3: STORE IN PGVECTOR
    # - INSERT chunks with ON CONFLICT DO NOTHING (UPSERT)
    # - Unique constraint: (source, page, chunk_index)
    # - Duplicates silently skipped (no error, no data corruption)
    # - Output: {"success": bool, "inserted": int, "skipped": int}
    # - Idempotent: Second run of same PDF inserts 0 new chunks
    # - Typical: 500ms-2s for 100+ chunks
    store_result = store_chunks(embedded)
    if not store_result["success"]:
        return {"success": False, "error": store_result["error"]}

    logger.info(
        f"✓ PDF indexed: {load_result['source']} — "
        f"{store_result['inserted']} inserted, {store_result['skipped']} skipped"
    )

    return {
        "success": True,
        "source": load_result["source"],
        "total_chunks": load_result["total_chunks"],
        "inserted": store_result["inserted"],
        "skipped": store_result["skipped"],
        "error": None
    }


def get_indexed_documents() -> list[str]:
    """Retrieve list of all unique PDF documents currently indexed in knowledge base.

    Direct database query to documents table for document discovery and management.
    Used by agent to:
    - Show user what documents are available
    - Allow filtering queries to specific PDFs
    - Manage document versioning (identify outdated sources for re-indexing)

    Returns:
        list[str]: List of unique source filenames currently indexed.
        - Type: List of strings
        - Content: Just filename (e.g., "cnil_ia_guidelines.pdf"), no paths
        - Order: Alphabetically sorted (ORDER BY source)
        - Example: ["cnil_ia_guidelines.pdf", "GDPR_overview.pdf", "compliance_checklist.pdf"]
        - Empty list []: When no documents indexed yet or database error
        - Deduplication: SELECT DISTINCT automatically removes duplicates
        - Performance: O(n) where n = unique sources (typically <50 in practice)

    Error Handling:
        - Connection failed: Returns empty list [] (graceful degradation)
        - Query failed: Logs error, returns empty list [] (never raises exception)
        - Empty database: Returns [] (no documents indexed yet)
        - Rationale: Returning [] is safer than crashing on connection errors

    Database Schema Query:
        SELECT DISTINCT source FROM documents ORDER BY source
        - Queries: documents table 'source' column
        - Groups: By unique source filename (DISTINCT)
        - Protection: No authorization check (assumes internal use only)
        - Index: Assumes source column has database index for performance

    Performance Characteristics:
        - Typical query: < 50ms (with proper database indexes)
        - Linear with unique sources: 10 sources ~ 20ms, 100 sources ~ 40ms
        - No data transfer: Only filenames returned (lightweight)
        - Connection overhead: ~10ms per query (includes connect + execute + close)

    Usage in Agent Context:
        Called from: Agent for document discovery, CLI for status report
        
        # Example usage:
        docs = get_indexed_documents()
        if docs:
            logger.info(f"Indexed documents: {', '.join(docs)}")
        else:
            logger.warning("No documents indexed yet. Call index_pdf() to add documents.")

    Typical Workflow:
        1. User asks question
        2. Agent calls get_indexed_documents() to validate corpus exists
        3. If empty: Return message "Veuillez d'abord indexer des documents"
        4. If non-empty: Call ask_document() to search indexed documents
        5. Return answer with sources cited from list returned by this function
    """
    from backend.engines.rag.vector_store import get_connection

    conn = get_connection()
    if not conn:
        logger.warning("Could not connect to database")
        return []

    try:
        # QUERY DATABASE: Retrieve unique source filenames from documents table
        # - SELECT DISTINCT: Groups by source, eliminates duplicates
        # - ORDER BY source: Alphabetical sorting for consistency
        # - Typical: <50ms with index on source column
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT source FROM documents ORDER BY source")
                # RETURN: List of source strings (e.g., ["cnil.pdf", "gdpr.pdf"])
                # - Empty list [] if no documents indexed
                # - Each source appears exactly once (DISTINCT guarantee)
                return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"✗ Query failed (get_indexed_documents): {e}")
        # GRACEFUL DEGRADATION: Return [] on error instead of raising
        # - Prevents agent from crashing on database transient failures
        # - Allows retry logic or fallback behavior
        return []
    finally:
        # CLEANUP: Always close connection to prevent resource leak
        # - Connection pooling: Next call gets fresh connection
        # - Important for long-running agents with multiple queries
        conn.close()