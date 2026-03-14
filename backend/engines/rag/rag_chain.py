"""RAG Orchestration Pipeline: Question-Answering with Context Retrieval.

Full Retrieval-Augmented Generation (RAG) pipeline for Analyse_IA.
Combines semantic search with LLM-powered answer generation in French.

Architecture:
- Query embedding: Convert user question to 768-dim vector (Ollama nomic-embed-text)
- Semantic search: Retrieve top-K most similar chunks from vector database (pgvector)
- Prompt engineering: Build French-language RAG prompt with context and sources
- LLM generation: Generate answer using mistral-nemo via Ollama API
- Source attribution: Return relevant document links for transparency

Pipeline flow:
  Question → Embed → Search → Retrieve chunks → Format prompt → Generate answer → Return results

Key features:
- Single-turn question answering (no conversation history)
- Source attribution with similarity scores and page numbers
- French output with instruction-based generation (temperature=0.1 for consistency)
- Context truncation (max 3000 chars) to prevent token overflow
- Graceful fallback when no relevant chunks found

Configuration:
- LLM: mistral-nemo:latest via Ollama (localhost:11434)
- Temperature: 0.1 (low randomness for consistent, factual responses)
- Top-k: 5 chunks (configurable, typical range 3-10)
- Timeout: 120s for LLM generation (large responses may need time)

Example usage:
    result = ask("Quels sont les droits des utilisateurs selon le RGPD?")
    if result['success']:
        print(result['answer'])
        for source in result['sources']:
            print(f"  - {source['source']} (page {source['page']})")
"""

import logging
import requests
from backend.engines.rag.embedding_engine import embed_text
from backend.engines.rag.vector_store import search_similar
from backend.utils.language import detect_language, translate_to_french

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
LLM_MODEL = "mistral-nemo:latest"
TOP_K = 5
MAX_CONTEXT_CHARS = 3000


def build_prompt(question: str, chunks: list[dict], language: str = 'fr') -> str:
    """Build a French RAG prompt with context and instructions.

    Formats retrieved chunks into a structured prompt with:
    - System instructions (respond only from context, cite sources, use French)
    - Ranked context (numbered sources with document names and pages)
    - User question
    - Response placeholder

    Process:
    1. Extract source, page, content from each chunk
    2. Number sources for easy reference (Source 1, Source 2, etc.)
    3. Frame each source with [Source N: filename, page M] header
    4. Join all sources with blank line separators for readability
    5. Truncate combined context to MAX_CONTEXT_CHARS if needed (prevent token overflow)
    6. Build French prompt template with instructions and context
    7. Return formatted prompt ready for LLM

    Args:
        question (str): User question in French or English
        chunks (list[dict]): Retrieved chunks from search_similar(), each containing:
            - content (str): Text passage
            - source (str): Filename or document name
            - page (int): Page number where chunk starts
            - similarity (float): Relevance score [0.0, 1.0] (not used in prompt, but available)

    Returns:
        str: Formatted prompt ready for mistral-nemo LLM generation

    Example:
        >>> chunks = [
        ...     {'source': 'RGPD.pdf', 'page': 5, 'content': 'Article 1...', 'similarity': 0.92},
        ...     {'source': 'Guide.pdf', 'page': 12, 'content': 'Section 2...', 'similarity': 0.88}
        ... ]
        >>> prompt = build_prompt("Quels droits?", chunks)
        >>> # Returns formatted French prompt with sources numbered [Source 1], [Source 2]

    Notes:
        - Context truncation: If combined length > MAX_CONTEXT_CHARS, cuts at MAX_CONTEXT_CHARS + "..."
        - Source numbering: Starts at 1 (not 0) for human readability
        - Language: Entire prompt in French (instructions + context sections)
        - Max context: 3000 chars to keep token count reasonable (~750 tokens)
    """
    context_parts = []

    # Format each chunk with source attribution for traceability
    for i, chunk in enumerate(chunks):
        source = chunk.get("source", "inconnu")  # Filename or doc name
        page = chunk.get("page", "?")             # Page number for reference
        content = chunk.get("content", "")        # Text passage
        # Number sources starting from 1 for human-readable references (Source 1, Source 2, etc.)
        context_parts.append(f"[Source {i+1}: {source}, page {page}]\n{content}")

    context = "\n\n".join(context_parts)

    # Prevent token overflow: truncate context if combined length exceeds limit
    # MAX_CONTEXT_CHARS=3000 roughly translates to ~750 tokens for mistral-nemo
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "..."

    # Construct RAG prompt with bilingual support:
    # - System instructions (respond only from context, cite sources, use selected language)
    # - Context from search results
    # - User question
    # - Response placeholder for LLM to complete
    if language == 'en':
        instruction = (
            "You are an expert assistant in data analysis and French regulation.\n"
            "Answer the question based ONLY on the provided context.\n"
            "If the context does not contain the answer, say so clearly.\n"
            "Always cite your sources (document name and page number).\n"
            "Answer in English."
        )
    else:
        instruction = (
            "Tu es un assistant expert en analyse de données et réglementation française.\n"
            "Réponds à la question en te basant UNIQUEMENT sur le contexte fourni.\n"
            "Si la réponse n'est pas dans le contexte, dis-le clairement.\n"
            "Cite toujours tes sources (nom du document et numéro de page).\n"
            "Réponds en français."
        )

    prompt = f"""{instruction}

CONTEXTE:
{context}

QUESTION: {question}

RÉPONSE:"""

    return prompt


def generate_answer(prompt: str) -> dict:
    """Send prompt to mistral-nemo LLM via Ollama API and retrieve answer.

    Calls mistral-nemo language model through Ollama REST API.
    Model is configured with low temperature (0.1) for factual, consistent responses.

    Process:
    1. Send POST request to Ollama /api/generate endpoint
    2. Set model to mistral-nemo:latest (must be pulled: ollama pull mistral-nemo)
    3. Configure generation parameters:
       - temperature=0.1 (low randomness, focus on likely tokens)
       - top_p=0.9 (nucleus sampling: keep top 90% of probability mass)
       - num_predict=512 (maximum 512 tokens per response)
    4. Send prompt and wait for completion (stream=False for full response)
    5. Extract response text, strip whitespace
    6. Return success dict with generated answer

    Args:
        prompt (str): Full RAG prompt from build_prompt() with context and question

    Returns:
        dict with keys:
        - success (bool): True if generation completed successfully
        - answer (str): Generated response text from LLM (post-processed, stripped)
        - error (str|None): Error message if success=False

    Logs:
        - ERROR: HTTP errors (non-200 status), empty responses, connection timeouts
        - General exceptions with stack trace

    Example:
        >>> result = generate_answer(prompt)
        >>> if result['success']:
        ...     print(result['answer'])
        # Output: "Selon le RGPD, les utilisateurs ont le droit à..."

    Error handling:
        - HTTP errors (non-200): checked immediately, specific error code logged
        - Empty response: checked after JSON parsing, likely model failure
        - Timeout (120s): caught specifically, common with slow systems
        - General exceptions: caught with full stack trace (unknown Ollama issues)

    Performance notes:
        - Typical response time: 5-30 seconds depending on model size and system
        - Temperature 0.1: Trades creativity for consistency/accuracy
        - num_predict=512: Typical RGPD/compliance answers fit in 200-400 tokens
        - Timeout 120s: Allows for slower GPU inference or busy systems

    Prerequisites:
        - Ollama running at localhost:11434
        - mistral-nemo:latest model pulled (ollama pull mistral-nemo)
        - Sufficient system memory (7B parameter model)
    """
    try:
        import os
        provider = os.getenv("LLM_PROVIDER", "ollama")

        if provider == "groq":
            from groq import Groq
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            chat_response = client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
                temperature=0.1,
            )
            answer = chat_response.choices[0].message.content.strip()
        else:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 512}
                },
                timeout=120
            )
            if response.status_code != 200:
                logger.error(f"✗ Ollama generate failed: HTTP {response.status_code}")
                return {"success": False, "error": f"Ollama error: {response.status_code}"}
            answer = response.json().get("response", "").strip()

        if not answer:
            logger.error("✗ Empty response from model")
            return {"success": False, "error": "Empty response from model"}
        logger.info(f"✓ Generated answer: {len(answer)} characters")
        return {"success": True, "answer": answer, "error": None}

    except requests.exceptions.Timeout:
        # LLM generation exceeded 120s timeout (system too slow or stalled)
        logger.error("✗ mistral-nemo timed out after 120s (system overloaded?)")
        return {"success": False, "error": "Model timeout"}

    except Exception as e:
        # Catch all other exceptions (connection loss, JSON parse errors, etc.)
        logger.error(f"✗ generate_answer failed: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


def ask(question: str, top_k: int = TOP_K) -> dict:
    """Full RAG pipeline orchestration: question → answer with sourced evidence.

    Core entry point for question-answering system. Chains all pipeline stages:
    embedding → retrieval → prompt engineering → LLM generation → source formatting.

    Pipeline stages:
    1. Validate question (non-empty, stripped)
    2. Embed question to 768-dim vector using Ollama nomic-embed-text
    3. Search vector database for top-K most similar chunks (cosine distance)
    4. Build French RAG prompt with retrieved context and instructions
    5. Generate answer using mistral-nemo with low temperature (0.1)
    6. Format results with source links (document name, page, similarity score)
    7. Return structured response dict

    Args:
        question (str): User question in French or English (ideally French for best results)
        top_k (int): Number of chunks to retrieve for context. Default TOP_K=5.
                    Typical range: 3-10 (more chunks = more context but longer processing)

    Returns:
        dict with keys:
        - success (bool): True if answer generated, False if failed at any stage
        - question (str): Original question (for reference)
        - answer (str): Generated answer in French (post-processed, ready to display)
        - sources (list[dict]): Attributed sources, each with:
            - source (str): Document name/filename
            - page (int): Page number where chunk found
            - similarity (float): Relevance score [0.0, 1.0] (higher = better match)
            - preview (str): First 100 chars + "..." (snippet for UI display)
        - chunks_used (int): Number of chunks used for answer generation (<= top_k)
        - error (str|None): Error message if success=False (helpful for debugging)

    Logs:
        - INFO: Query received (first 80 chars)
        - INFO: Chunks retrieved with top similarity score
        - INFO: Answer generated (character count)
        - WARNING: No relevant chunks found (graceful degradation)
        - ERROR: Embedding failure, search failure, generation failure

    Example:
        >>> result = ask("Quels sont les droits des utilisateurs selon le RGPD?")
        >>> if result['success']:
        ...     print(result['answer'])
        ...     for source in result['sources']:
        ...         print(f"  - {source['source']} (page {source['page']}, similarity {source['similarity']})")
        ...         print(f"    Preview: {source['preview']}")
        >>> else:
        ...     print(f"Error: {result['error']}")

    Error scenarios:
        1. Empty question: Returns error, logs nothing
        2. Embedding failure: Logs ERROR, returns error dict
        3. Search failure: Logs ERROR, returns error dict (with search error details)
        4. No chunks found: Logs WARNING, returns success=True with generic French fallback
        5. Generation failure: Returns error dict (search succeeded but LLM failed)

    Fallback behavior:
        - If no chunks found (empty search): Returns success=True with default French response
          "Je n'ai pas trouvé d'informations pertinentes..." (transparent to user)

    Performance notes:
        - Embedding: ~50-100ms (local Ollama)
        - Search: ~10-50ms (PostgreSQL pgvector with index)
        - Prompt building: <1ms
        - LLM generation: 5-30 seconds (depends on GPU/CPU)
        - Total: typically 5-35 seconds, dominated by LLM generation

    Pipeline robustness:
        - Graceful degradation: Each stage checks success, returns early on error
        - Error context: Error dict includes which stage failed
        - Source attribution: Always provided when chunks retrieved (transparency)
    """
    # INPUT VALIDATION: Ensure question is non-empty and meaningful
    if not question or not question.strip():
        return {"success": False, "error": "Empty question"}

    logger.info(f"→ RAG query received: {question[:80]}...")

    # STAGE 1: EMBEDDING — Convert question to 768-dim vector
    # Translate to French if English detected (improves similarity matching against French indexed chunks)
    query_language = detect_language(question)
    query_for_embedding = translate_to_french(question) if query_language == 'en' else question
    if query_language == 'en':
        logger.info(f"English query detected — translating for embedding")
    # This vector will be used to find semantically similar chunks in database
    query_embedding = embed_text(query_for_embedding)
    if query_embedding is None:
        logger.error("✗ Embedding failed (Ollama unavailable?)")
        return {"success": False, "error": "Failed to embed question"}

    # STAGE 2: RETRIEVAL — Search for top-K most similar chunks
    # Uses cosine distance in pgvector (lower distance = more similar)
    search_result = search_similar(query_embedding, top_k=top_k)
    if not search_result["success"]:
        logger.error(f"✗ Search failed: {search_result['error']}")
        return {"success": False, "error": search_result["error"]}

    chunks = search_result["results"]

    # Edge case: No relevant context found in database
    # Return success=True with graceful fallback message (don't crash UI)
    if not chunks:
        logger.warning(f"⚠ No relevant chunks found for: {question[:60]}...")
        return {
            "success": True,
            "question": question,
            "answer": "Je n'ai pas trouvé d'informations pertinentes dans les documents disponibles pour répondre à cette question.",
            "sources": [],
            "chunks_used": 0,
            "error": None
        }

    logger.info(f"✓ Retrieved {len(chunks)} chunks, top similarity: {chunks[0]['similarity']:.4f}")

    # STAGE 3: PROMPT ENGINEERING — Build bilingual RAG prompt with instructions
    # This combines system instructions, context (chunks), and question
    # Instructs model to use only provided context and cite sources
    # Language selected from detected query language (French or English)
    prompt = build_prompt(question, chunks, language=query_language)

    # STAGE 4: GENERATION — Send prompt to LLM, wait for answer
    # mistral-nemo responds in French with source citations and reasoning
    generation = generate_answer(prompt)
    if not generation["success"]:
        logger.error(f"✗ Generation failed: {generation['error']}")
        return {"success": False, "error": generation["error"]}

    # STAGE 5: SOURCE FORMATTING — Prepare attribution for UI display
    # Extract key metadata (source, page, similarity) and preview text
    # Preview shows first 100 chars to help user verify source relevance
    sources = [
        {
            "source": c["source"],           # Document/file name
            "page": c["page"],               # Page number for quick reference
            "similarity": c["similarity"],   # Relevance score [0.0, 1.0]
            "preview": c["content"][:100] + "..."  # Text preview for verification
        }
        for c in chunks
    ]

    logger.info(f"✓ RAG complete: Generated {len(generation['answer'])} char answer from {len(chunks)} chunks")

    # Return complete structured response
    return {
        "success": True,
        "question": question,
        "answer": generation["answer"],    # Main output: generated answer in French
        "sources": sources,                # Source attribution with links
        "chunks_used": len(chunks),        # Transparency: how many chunks used
        "error": None
    }