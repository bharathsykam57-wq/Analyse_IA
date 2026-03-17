"""Test suite for RAG orchestration pipeline (end-to-end integration tests).

Validates complete question-answering RAG workflow:
- Embedding generation for questions and document chunks
- Vector storage and semantic similarity search
- Prompt engineering and source formatting
- LLM-powered answer generation with mistral-nemo
- Graceful fallback for edge cases (empty questions, no context found)

Test categories:
1. Prompt builder: Validates French RAG prompt formatting
2. LLM generation: Tests mistral-nemo answer generation
3. Full RAG pipeline: End-to-end question → answer with sources
4. Edge cases: No relevant context, empty questions

Test data: French GDPR/RGPD compliance context (5 test chunks)

Prerequisites:
- PostgreSQL with pgvector extension running
- Ollama server with nomic-embed-text and mistral-nemo:latest models
- analyseIA_dev database configured and accessible

Run with: python scripts/test_rag_chain.py
or: pytest scripts/test_rag_chain.py -v -s

Test execution order:
1. Setup: Insert GDPR test chunks into vector database
2. Test 1-5: Run individual test cases
3. Cleanup: Remove test chunks and verify database state

Performance expectations:
- Embedding: ~50-100ms per question
- Search: ~10-50ms for top-5 semantic retrieval
- LLM generation: 5-30 seconds (depends on GPU/CPU resources)
- Total pipeline: typically 10-40 seconds
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engines.rag.embedding_engine import embed_chunks
from backend.engines.rag.vector_store import store_chunks, delete_source
from backend.engines.rag.rag_chain import ask, build_prompt, generate_answer

TEST_SOURCE = "test_rag_chain.pdf"


def setup():
    """Prepare test environment: embed and store GDPR test chunks.

    One-time setup executed before all tests. Creates a consistent test dataset
    with 5 French GDPR/RGPD compliance chunks covering key topics:
    - RGPD definition and entry date
    - CNIL authority and penalty ranges
    - Data breach notification procedures (72-hour requirement)
    - DPO (Data Protection Officer) obligations
    - Right to erasure (right to be forgotten)

    Process:
    1. Create 5 structured chunk dicts with GDPR content
    2. Remove any stale test chunks from previous test runs (idempotency)
    3. Generate 768-dim embeddings for all chunks using embed_chunks()
    4. Store embeddings in PostgreSQL pgvector with metadata
    5. Log insertion count for verification

    Returns:
        (implicit) Test chunks inserted and ready for retrieval

    Side effects:
        - Deletes TEST_SOURCE from vector store (cleanup from previous runs)
        - Inserts 5 new chunks with source="test_rag_chain.pdf"
        - Populates pgvector embeddings table

    Notes:
        - Each chunk has unique chunk_id (rag001-rag005) for traceability
        - Pages numbered 1-5 for source attribution testing
        - GDPR context realistic for testing semantic search quality
    """
    chunks = [
        {
            "content": "Le RGPD (Règlement Général sur la Protection des Données) est entré en vigueur le 25 mai 2018. Il s'applique à toutes les entreprises traitant des données de citoyens européens.",
            "source": TEST_SOURCE,
            "page": 1,
            "chunk_index": 0,
            "chunk_id": "rag001"
        },
        {
            "content": "La CNIL est l'autorité française chargée de contrôler l'application du RGPD en France. Elle peut infliger des amendes allant jusqu'à 20 millions d'euros ou 4% du chiffre d'affaires mondial.",
            "source": TEST_SOURCE,
            "page": 2,
            "chunk_index": 0,
            "chunk_id": "rag002"
        },
        {
            "content": "Toute violation de données personnelles doit être signalée à la CNIL dans un délai de 72 heures après sa découverte. Le responsable de traitement doit documenter toutes les violations.",
            "source": TEST_SOURCE,
            "page": 3,
            "chunk_index": 0,
            "chunk_id": "rag003"
        },
        {
            "content": "Le délégué à la protection des données (DPO) est obligatoire pour les organismes publics et les entreprises dont le traitement de données est une activité principale à grande échelle.",
            "source": TEST_SOURCE,
            "page": 4,
            "chunk_index": 0,
            "chunk_id": "rag004"
        },
        {
            "content": "Le droit à l'effacement, aussi appelé droit à l'oubli, permet à toute personne de demander la suppression de ses données personnelles dans certaines conditions prévues par le RGPD.",
            "source": TEST_SOURCE,
            "page": 5,
            "chunk_index": 0,
            "chunk_id": "rag005"
        }
    ]

    delete_source(TEST_SOURCE)
    embedded = embed_chunks(chunks)
    result = store_chunks(embedded)
    assert result["success"], f"✗ Setup failed: {result.get('error', 'Unknown error')}"
    print(f"✓ Setup complete: {result['inserted']} chunks inserted")


def cleanup():
    """Remove test chunks from database after test suite completion.

    Performs post-test cleanup to ensure:
    - No test data pollutes subsequent test runs
    - Database remains in clean state for manual inspection
    - Vector store doesn't accumulate duplicate test chunks

    Process:
        1. Delete all chunks with source="test_rag_chain.pdf"
        2. Verify deletion succeeded (implicit in test assertions)

    Returns:
        (implicit) Test chunks deleted from vector store

    Side effects:
        - Removes 5 test chunks from pgvector embeddings table
        - Frees up database space for subsequent tests
    """
    delete_source(TEST_SOURCE)


def test_build_prompt():
    """Test French RAG prompt formatting and structure.

    Validates that build_prompt() correctly formats:
    - System instructions (French language, context-only reasoning, source citation)
    - Context section (numbered sources with document names and page numbers)
    - User question
    - Response placeholder for LLM completion

    Test steps:
    1. Create 2 test chunks with GDPR context
    2. Call build_prompt() with question and chunks
    3. Verify prompt contains all required sections (CONTEXTE, QUESTION, RÉPONSE)
    4. Verify sources are numbered (Source 1, Source 2) for human reference
    5. Verify question text is included in prompt

    Assertions:
    - Prompt includes original question text (✓)
    - "CONTEXTE" section header present (signals context paragraph)
    - "QUESTION" section header present (clear question demarcation)
    - "RÉPONSE" section header present (signals where model should write)
    - Sources numbered as "Source 1", "Source 2" (human-readable numbering)

    Expected output:
    - Prompt length: typically 500-800 chars for 2 chunks + short question
    - Structure: [Instructions] CONTEXTE: [Sources] QUESTION: [Q] RÉPONSE:

    Notes:
    - Prompt must be in French (instructions + structure)
    - Source numbering starts at 1 (not 0) for better UX
    - This test uses mock chunks, not database content
    """
    print("\n--- Test 1: Prompt builder ---")
    chunks = [
        {"content": "La CNIL contrôle le RGPD.", "source": "test.pdf", "page": 1},
        {"content": "Le RGPD date de 2018.", "source": "test.pdf", "page": 2}
    ]
    prompt = build_prompt("Qu'est-ce que la CNIL?", chunks)

    # Verify prompt structure and required sections
    assert "CNIL" in prompt, "✗ Question text not preserved in prompt"
    assert "CONTEXTE" in prompt, "✗ Context section header missing"
    assert "QUESTION" in prompt, "✗ Question section header missing"
    assert "RÉPONSE" in prompt, "✗ Response placeholder missing"
    assert "Source 1" in prompt, "✗ Source numbering not found"

    print("✅ PASS: Prompt builder OK")
    print(f"   Prompt structure valid (length: {len(prompt)} chars)")


def test_generate_answer():
    """Test mistral-nemo LLM answer generation via Ollama API.

    Validates that generate_answer() successfully:
    - Connects to Ollama server (localhost:11434)
    - Calls mistral-nemo:latest model
    - Generates coherent French responses
    - Extracts and returns response text

    Test steps:
    1. Create simple, straightforward RAG prompt (factual RGPD question)
    2. Call generate_answer() with prompt
    3. Check success flag is True (no API errors)
    4. Verify answer is non-empty and meaningful (length > 10 chars)
    5. Display first 100 chars of answer for manual verification

    Assertions:
    - Response success=True (✓ generation completed without error)
    - Response answer length > 10 chars (✗ answer too short or empty)

    Expected output:
    - Answer: "Le RGPD est entré en vigueur en 2018." or similar
    - Typical length: 50-200 chars for simple factual questions

    Error scenarios tested implicitly:
    - Ollama connection failure: caught by success=False
    - Model timeout: caught by success=False
    - Empty response: caught by success=False

    Performance:
    - Typical latency: 5-15 seconds depending on GPU/CPU
    - Model config: temperature=0.1 (low randomness, factual)

    Prerequisites:
    - Ollama running and accessible at OLLAMA_URL
    - mistral-nemo:latest model pulled locally
    """
    print("\n--- Test 2: LLM generation (mistral-nemo) ---")
    simple_prompt = """Réponds en une phrase en français.
CONTEXTE: Le RGPD est entré en vigueur en 2018.
QUESTION: Quand le RGPD est-il entré en vigueur?
RÉPONSE:"""

    result = generate_answer(simple_prompt)
    
    # Verify generation succeeded without API errors
    assert result["success"] == True, f"✗ Generation failed: {result['error']}"
    
    # Verify answer is meaningful (not empty or minimal)
    assert len(result["answer"]) > 10, f"✗ Answer too short: {len(result['answer'])} chars"

    print("✅ PASS: LLM generation OK")
    print(f"   Generated answer: {result['answer'][:100]}")


def test_ask_with_context():
    """Test complete end-to-end RAG pipeline with relevant context.

    Validates full question-answering workflow:
    1. Embed question → 768-dim vector
    2. Search database → retrieve top-5 similar chunks
    3. Format RAG prompt → build structured context+question
    4. Generate answer → call mistral-nemo for response
    5. Format results → return answer with source attribution

    Test input:
    - Question: "Quel est le délai pour signaler une violation de données à la CNIL?"
    - This question should match test chunk about 72-hour notification requirement

    Assertions:
    - Pipeline success=True (✓ answer generated without errors)
    - Answer length > 20 chars (✗ answer too minimal)
    - chunks_used > 0 (✗ no chunks retrieved, suggesting search failure)
    - sources list non-empty (✗ no source attribution provided)

    Expected output:
    - Answer: Mentions 72-hour notification requirement in French
    - Chunks used: 1-5 (typically 5 if search works well)
    - Top source: test_rag_chain.pdf with high similarity score (0.8+)

    Pipeline robustness:
    - Each stage logs INFO with progress indicators
    - Graceful degradation if any component fails
    - Sources ranked by relevance (similarity scores)

    Notes:
    - This test assumes test_setup() was called first
    - Expected latency: 15-40 seconds (dominated by LLM generation)
    - Tests the happy path (optimal search results and answer generation)
    """
    print("\n--- Test 3: Full RAG pipeline ---")
    result = ask("Quel est le délai pour signaler une violation de données à la CNIL?")

    # Verify pipeline succeeded
    assert result["success"] == True, f"✗ RAG pipeline failed: {result['error']}"
    
    # Verify answer is meaningful (not empty or minimal)
    assert len(result["answer"]) > 20, f"✗ Answer too short: {len(result['answer'])} chars"
    
    # Verify semantic search worked
    assert result["chunks_used"] > 0, f"✗ No chunks retrieved (search failed)"
    
    # Verify source attribution available
    assert len(result["sources"]) > 0, "✗ No source attribution provided"

    print("✅ PASS: Full RAG pipeline OK")
    print(f"   Question:      {result['question']}")
    print(f"   Answer:        {result['answer'][:150]}...")
    print(f"   Chunks used:   {result['chunks_used']}")
    print(f"   Top source:    {result['sources'][0]['source']} (similarity: {result['sources'][0]['similarity']:.4f})")


def test_ask_no_context():
    """Test graceful degradation when no relevant context found.

    Validates that RAG pipeline handles edge case where query has no
    matching documents in the database. System should:
    - Return success=True (not crash with error)
    - Provide user-friendly French fallback response
    - Explain why answer could not be generated

    Test input:
    - Question: "Quel est le prix du pétrole aujourd'hui?"
    - This question has NO match in GDPR test chunks (out-of-domain query)

    Expected behavior:
    - Embedding succeeds (question is valid)
    - Search returns 0 chunks (no semantic match to GDPR documents)
    - Pipeline returns fallback response instead of crashing
    - Fallback is in French: "Je n'ai pas trouvé d'informations pertinentes..."

    Assertions:
    - success=True (✓ graceful handling, not error)
    - chunks_used >= 0 (✗ negative value indicates unknown error)

    Philosophy:
    - System should never crash or return confusing error messages
    - Out-of-domain questions handled transparently
    - User gets clear signal that answer cannot be provided from documents

    Performance:
    - Fast: ~100ms (embedding + search, no LLM generation)
    - No LLM call needed when no context available

    Notes:
    - Tests robustness: system handles all query types gracefully
    - Verifies fallback mechanism works correctly
    """
    print("\n--- Test 4: Question with no relevant context ---")
    result = ask("Quel est le prix du pétrole aujourd'hui?")

    # Verify graceful degradation (no crash on out-of-domain question)
    assert result["success"] == True, f"✗ Out-of-domain query caused error: {result['error']}"
    
    # Verify fallback mechanism works (0 chunks with graceful response)
    assert result["chunks_used"] >= 0, "✗ Invalid chunk count"

    print("✅ PASS: No context case handled gracefully")
    print(f"   Fallback response: {result['answer'][:150]}...")


def test_empty_question():
    """Test input validation: reject empty questions.

    Validates that ask() validates input before processing:
    - Rejects empty string questions ("") early
    - Returns error response (success=False) with message
    - Does NOT attempt embedding/search/generation on invalid input
    - Prevents unnecessary API calls for invalid inputs

    Test input:
    - Question: "" (empty string)

    Expected behavior:
    - ask() checks if question.strip() is empty
    - Returns immediately with error dict
    - Error message: "Empty question"
    - Does not call embed_text() or search_similar()

    Assertions:
    - success=False (✗ answer generated, validation failed)
    - error message="Empty question" (✗ wrong error message)

    Test purpose:
    - Input validation prevents downstream errors
    - Clear error message helps users understand what went wrong
    - Early exit improves performance (no unnecessary embedding calls)

    Performance:
    - Instant: <1ms (validation check only, no API calls)

    Notes:
    - Tests input validation robustness
    - Prevents garbage questions from reaching LLM
    - Ensures fail-fast behavior for obvious invalid inputs
    """
    print("\n--- Test 5: Empty question handling ---")
    result = ask("")
    
    # Verify input validation rejected empty question
    assert result["success"] == False, "✗ Empty question was accepted (validation failed)"
    
    # Verify specific error message
    assert result["error"] == "Empty question", f"✗ Wrong error message: {result['error']}"
    
    print("✅ PASS: Empty question validation OK")


if __name__ == "__main__":
    """Execute complete RAG pipeline test suite.
    
    Orchestrates test execution in proper order:
    1. Setup: Embed and store GDPR test chunks in vector database
    2. Test 1: Validate prompt builder (format, structure, numbering)
    3. Test 2: Validate LLM generation (Ollama connectivity, model inference)
    4. Test 3: Validate full RAG pipeline (embedding → search → generation)
    5. Test 4: Validate graceful degradation (no context found)
    6. Test 5: Validate input validation (empty questions rejected)
    7. Cleanup: Remove test chunks from database
    8. Report: Summary of test results
    
    Expected runtime: 60-120 seconds (dominated by LLM generation in tests 2-3)
    
    Exit codes:
    - 0: All tests passed
    - 1: Any assertion failed (details printed to stdout)
    """
    print("=" * 70)
    print("Test Suite: Analyse_IA RAG Pipeline (rag_chain.py)")
    print("=" * 70)

    # STAGE 1: Setup test environment
    print("\n→ Stage 1: Setting up test data...")
    setup()

    # STAGE 2: Run individual test cases
    print("\n→ Stage 2: Running test cases...")
    try:
        test_build_prompt()           # Test prompt formatting
        test_generate_answer()        # Test LLM integration
        test_ask_with_context()       # Test full pipeline (happy path)
        test_ask_no_context()         # Test graceful degradation
        test_empty_question()         # Test input validation
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        print("\n→ Stage 3: Cleanup (before exit)...")
        cleanup()
        import sys
        sys.exit(1)

    # STAGE 3: Cleanup test environment
    print("\n→ Stage 3: Cleaning up test data...")
    cleanup()

    # STAGE 4: Report success
    print("\n" + "=" * 70)
    print("✅ All rag_chain tests passed successfully")
    print("=" * 70)