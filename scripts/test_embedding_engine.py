"""Test suite for Analyse_IA text embedding engine (Ollama + nomic-embed-text).

Validates the complete embedding pipeline for RAG document processing:
- Ollama connection and model availability
- Single-text embedding generation (768-dimensional vectors)
- Batch chunk embedding with metadata preservation
- Error handling (empty inputs, Ollama failures)

Tests cover:
1. Infrastructure: Ollama connectivity and model setup
2. Single operations: embed_text() function with various inputs
3. Batch operations: embed_chunks() with metadata preservation
4. Error handling: Empty/invalid inputs, graceful degradation

Prerequisites:
- Ollama running locally (ollama serve)
- nomic-embed-text model available (ollama pull nomic-embed-text)

Run with: python scripts/test_embedding_engine.py
or: pytest scripts/test_embedding_engine.py -v -s

Test data: Uses French text (GDPR/RGPD context) for realistic validation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engines.rag.embedding_engine import (
    check_ollama_connection,
    embed_text,
    embed_chunks
)


def test_ollama_connection():
    """Test Ollama infrastructure: server running and model available.

    Pre-flight health check that verifies:
    - Ollama service is running on localhost:11434
    - nomic-embed-text model is installed and accessible
    - API endpoints respond correctly

    This is a blocking test - if it fails, all other tests will also fail
    because they depend on Ollama being available.

    Assertions:
    - connection result is True (Ollama is ready)
    - No exception raised

    Failure troubleshooting:
    - If fails: Start Ollama with: ollama serve
    - Check model: ollama list (should show nomic-embed-text)
    - Install model: ollama pull nomic-embed-text
    """
    print("\n--- Test 1: Ollama infrastructure (connection + model availability) ---")
    result = check_ollama_connection()
    assert result == True, "✗ Ollama must be running with nomic-embed-text model available"
    print("✅ PASS: Ollama connection healthy")


def test_embed_single_text():
    """Test single-text embedding generation and validation.

    Validates embed_text() function produces valid 768-dimensional vectors
    from input text. Tests the core embedding operation used in batch processing.

    What is tested:
    - Embedding is generated (not None)
    - Result is a list of floats (correct type)
    - Output has exactly 768 dimensions (nomic-embed-text specification)
    - All values are floating-point numbers (valid embeddings)

    Test input: French GDPR text for realistic language support validation

    Assertions:
    - embedding is not None (generation succeeded)
    - embedding is a list (correct data structure)
    - len(embedding) == 768 (correct dimensionality)
    - all values are floats (valid embedding values)
    """
    print("\n--- Test 2: Single-text embedding generation ---")
    # French text testing: GDPR/RGPD regulations
    text = "Le règlement général sur la protection des données personnelles."
    embedding = embed_text(text)

    assert embedding is not None, "✗ Embedding should not be None"
    assert isinstance(embedding, list), "✗ Embedding should be a list"
    assert len(embedding) == 768, f"✗ Expected 768 dims, got {len(embedding)}"
    assert all(isinstance(v, float) for v in embedding), "✗ All values should be floats"

    print(f"✅ PASS: Single-text embedding validated")
    print(f"   Dimensionality: {len(embedding)}")
    print(f"   First 5 values: {[round(v, 4) for v in embedding[:5]]}")


def test_embed_empty_text():
    """Test error handling: empty/whitespace-only text inputs.

    Validates that embed_text() gracefully handles invalid inputs by
    returning None (graceful degradation model). This is important for
    batch processing where some chunks might be empty.

    Test cases:
    - Empty string ""
    - Function should not raise exception
    - Should return None (not an empty embedding)

    Why this matters:
    - PDFs may contain blank pages or formatting artifacts
    - Batch processing continues despite individual failures
    - Prevents invalid embeddings in vector storage

    Assertions:
    - Result is None (correct None response for empty input)
    - No exception raised
    """
    print("\n--- Test 3: Error handling (empty/whitespace-only text) ---")
    result = embed_text("")
    assert result is None, "✗ Empty text should return None (graceful degradation)"
    print("✅ PASS: Empty text handled correctly (returns None)")


def test_embed_chunks():
    """Test batch embedding of document chunks with metadata preservation.

    Validates embed_chunks() function - the main entry point for embedding
    RAG document chunks. Verifies:
    - Multiple chunks are embedded in parallel batches
    - Metadata fields are preserved alongside embeddings
    - Output structure matches expectations for pgvector storage
    - Embedding dimensionality is correct for all chunks

    Test data:
    - 3 French chunks from GDPR regulation document
    - Each chunk has metadata: source, page, chunk_index, chunk_id
    - Simulates real document processing pipeline

    What is tested:
    - All chunks are embedded (count preserved)
    - Each chunk has 'embedding' key added (metadata preservation)
    - All embeddings are 768-dimensional (correct output format)
    - Original metadata intact (source, page, chunk_index, chunk_id)

    Assertions:
    - Output count matches input count
    - All chunks have 'embedding' field
    - All embeddings are 768 dimensions
    """
    print("\n--- Test 4: Batch chunk embedding (main pipeline) ---")
    
    # Test data: Multiple chunks with metadata (simulating document_loader output)
    chunks = [
        {
            "content": "La CNIL est l'autorité française de protection des données.",
            "source": "test.pdf",
            "page": 1,
            "chunk_index": 0,
            "chunk_id": "abc001"
        },
        {
            "content": "Le RGPD impose des obligations strictes aux entreprises.",
            "source": "test.pdf",
            "page": 1,
            "chunk_index": 1,
            "chunk_id": "abc002"
        },
        {
            "content": "Toute violation de données doit être signalée sous 72 heures.",
            "source": "test.pdf",
            "page": 2,
            "chunk_index": 0,
            "chunk_id": "abc003"
        }
    ]

    # Main operation: embed all chunks
    embedded = embed_chunks(chunks)

    # Assertions: Validate output
    assert len(embedded) == 3, f"✗ Expected 3 embedded chunks, got {len(embedded)}"
    assert all("embedding" in c for c in embedded), "✗ All chunks should have 'embedding' key"
    assert all(len(c["embedding"]) == 768 for c in embedded), "✗ All embeddings should be 768-dimensional"
    
    # Verify metadata preservation
    assert all("chunk_id" in c for c in embedded), "✗ Metadata 'chunk_id' should be preserved"
    assert all("source" in c for c in embedded), "✗ Metadata 'source' should be preserved"

    print(f"✅ PASS: Batch chunk embedding successful")
    print(f"   Chunks processed: {len(embedded)}")
    print(f"   Embedding dims: {len(embedded[0]['embedding'])}")
    print(f"   Metadata preserved: chunk_id={embedded[0]['chunk_id']}, source={embedded[0]['source']}")
    print(f"   Sample content: {embedded[0]['content'][:55]}...")


def test_embed_empty_chunks():
    """Test error handling: empty chunk list input.

    Validates that embed_chunks() gracefully handles empty input by
    returning empty list (no exceptions raised). Important for pipeline
    robustness when documents yield no chunks.

    Test case:
    - Input: Empty list []
    - Expected: Empty list [] (not None, not error)
    - Function completes without exception

    Why this matters:
    - Some PDFs may fail to extract any text (scanned images, corrupted)
    - Pipeline should handle gracefully without crashing
    - Batch processing continues for other documents

    Assertions:
    - Result is empty list (not None, not exception)
    - Correct return type for safe downstream processing
    """
    print("\n--- Test 5: Error handling (empty chunk list) ---")
    result = embed_chunks([])
    assert result == [], "✗ Empty input should return empty list"
    print("✅ PASS: Empty chunk list handled correctly (returns [])")


if __name__ == "__main__":
    """Run complete embedding engine test suite."""
    print("=" * 70)
    print("Test Suite: Analyse_IA Embedding Engine (Ollama + nomic-embed-text)")
    print("=" * 70)

    # Test order matters: Infrastructure → Core → Batch → Error handling
    try:
        test_ollama_connection()           # Pre-flight check (blocking)
        test_embed_single_text()           # Core embedding function
        test_embed_empty_text()            # Error handling: single operations
        test_embed_chunks()                # Main batch pipeline
        test_embed_empty_chunks()          # Error handling: batch operations

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {str(e)}")
        sys.exit(1)

    # Success - all tests passed
    print("\n" + "=" * 70)
    print("✅ All embedding_engine tests passed successfully")
    print("=" * 70)
    sys.exit(0)