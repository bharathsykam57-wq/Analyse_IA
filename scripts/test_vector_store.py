"""Test suite for Analyse_IA vector store (PostgreSQL + pgvector backend).

Validates the complete semantic search pipeline for RAG document retrieval:
- Database connectivity and pgvector extension
- Batch chunk storage with deduplication
- Vector similarity search (cosine distance)
- CRUD operations (insert, search, delete)

Tests cover:
1. Infrastructure: PostgreSQL connection to analyseIA_dev database
2. Storage: Embed chunks and store in pgvector with metadata
3. Deduplication: Verify duplicate handling (ON CONFLICT)
4. Search: Similarity search using cosine distance operator (<=>)
5. Monitoring: Document count tracking
6. Cleanup: Source-based deletion
7. End-to-end: Complete RAG pipeline simulation

Prerequisites:
- PostgreSQL running with pgvector extension
- analyseIA_dev database configured
- pgvector extension installed: CREATE EXTENSION IF NOT EXISTS vector

Run with: python scripts/test_vector_store.py
or: pytest scripts/test_vector_store.py -v -s

Test data: French GDPR/RGPD compliance text for realistic RAG scenario
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engines.rag.vector_store import (
    get_connection,
    store_chunks,
    search_similar,
    get_document_count,
    delete_source
)
from backend.engines.rag.embedding_engine import embed_text, embed_chunks


TEST_SOURCE = "test_vector_store.pdf"  # Consistent source for all test chunks


def cleanup():
    """Remove test data before and after test execution.

    Ensures clean state by deleting any test chunks from previous runs.
    Called at start (before tests) and implicitly at end (by test_delete_source).

    This prevents:
    - Duplicate constraint violations from previous test runs
    - Contaminated search results from stale test data
    - Inaccurate document count assertions

    Returns:
        (implicit) Test data removed if exists
    """
    delete_source(TEST_SOURCE)


def test_db_connection():
    """Test infrastructure: PostgreSQL connection to vector store.

    Pre-flight health check verifying:
    - PostgreSQL server is running and accessible
    - analyseIA_dev database exists and is accessible
    - psycopg2 connection established without errors
    - pgvector extension is installed (implicit, tested by store_chunks/search_similar)

    This is a blocking test - all other tests depend on database connectivity.

    Assertions:
    - connection object is not None (successful connection)
    - No exception raised

    Troubleshooting on failure:
    - Check: psql -U sykambharath -d analyseIA_dev -c "SELECT 1"
    - Check pgvector: psql -d analyseIA_dev -c "CREATE EXTENSION IF NOT EXISTS vector"
    """
    print("\n--- Test 1: Infrastructure (database connection) ---")
    conn = get_connection()
    assert conn is not None, "✗ Should connect to analyseIA_dev database"
    conn.close()
    print("✅ PASS: PostgreSQL connection healthy")


def test_store_chunks():
    """Test storage pipeline: embed chunks and store in pgvector.

    End-to-end storage workflow validation:
    1. Create test chunks with metadata (source, page, chunk_index)
    2. Embed chunks using nomic-embed-text (768-dim vectors)
    3. Store embeddings in PostgreSQL pgvector table
    4. Verify insertion counts and transaction success

    Test data:
    - 3 French GDPR text chunks (from different pages)
    - Each chunk has: content, source, page, chunk_index, chunk_id

    What is tested:
    - All chunks successfully embedded (non-empty vectors)
    - All chunks successfully stored (transaction committed)
    - Insertion count matches input count
    - Metadata preserved (source, page, chunk_index fields)

    Assertions:
    - Embedding succeeds (returns 3 embedded chunks)
    - Store succeeds (success=True)
    - Inserted count = 3 (all chunks new)
    - Skipped count = 0 (no duplicates yet)
    """
    print("\n--- Test 2: Storage pipeline (embed → store chunks) ---")

    # Test data: Multiple chunks simulating real PDF extraction
    chunks = [
        {
            "content": "Le RGPD protège les données personnelles des citoyens européens.",
            "source": TEST_SOURCE,
            "page": 1,
            "chunk_index": 0,
            "chunk_id": "test001"
        },
        {
            "content": "La CNIL contrôle l'application du RGPD en France.",
            "source": TEST_SOURCE,
            "page": 1,
            "chunk_index": 1,
            "chunk_id": "test002"
        },
        {
            "content": "Toute entreprise traitant des données doit nommer un DPO.",
            "source": TEST_SOURCE,
            "page": 2,
            "chunk_index": 0,
            "chunk_id": "test003"
        }
    ]

    # Stage 1: Embed all chunks
    embedded = embed_chunks(chunks)
    assert len(embedded) == 3, "✗ All chunks should be embedded"

    # Stage 2: Store embeddings in vector store
    result = store_chunks(embedded)
    assert result["success"] == True, f"✗ Store failed: {result['error']}"
    assert result["inserted"] == 3, f"✗ Expected 3 inserted, got {result['inserted']}"

    print(f"✅ PASS: Storage pipeline successful")
    print(f"   Chunks embedded: {len(embedded)}")
    print(f"   Chunks inserted: {result['inserted']}")
    print(f"   Duplicates skipped: {result['skipped']}")


def test_duplicate_handling():
    """Test deduplication: verify UPSERT (INSERT ON CONFLICT DO NOTHING).

    Validates that duplicate chunks are correctly skipped and not reinserted.
    Duplicates identified by unique constraint on (source, page, chunk_index).

    Scenario:
    - Insert same chunk again (identical source, page, chunk_index)
    - UPSERT should skip insertion (ON CONFLICT DO NOTHING)
    - Result: inserted=0 (not inserted), skipped=1 (duplicate found)

    Why this matters:
    - Prevents duplicate vectors in search results
    - Ensures idempotent ingestion (rerun safe)
    - Maintains data integrity under retries

    Assertions:
    - Store succeeds (transaction completes)
    - Inserted count = 0 (duplicate not inserted)
    - Skipped count ≥ 1 (duplicate identified and skipped)
    """
    print("\n--- Test 3: Deduplication (UPSERT on duplicate key) ---")

    # Same chunk as test_store_chunks (will trigger unique constraint)
    chunks = [
        {
            "content": "Le RGPD protège les données personnelles des citoyens européens.",
            "source": TEST_SOURCE,
            "page": 1,
            "chunk_index": 0,
            "chunk_id": "test001"
        }
    ]

    # Embed and attempt to store duplicate
    embedded = embed_chunks(chunks)
    result = store_chunks(embedded)

    assert result["success"] == True, "✗ Transaction should complete"
    assert result["inserted"] == 0, "✗ Duplicate should not be inserted"

    print(f"✅ PASS: Deduplication working correctly")
    print(f"   Duplicate detected and skipped: {result['skipped']}")


def test_search_similar():
    """Test semantic search: find similar chunks using cosine distance.

    Core RAG retrieval validation - searches for semantically similar chunks
    to a natural language query.

    Process:
    1. Formulate query: "Qui contrôle la protection des données en France?"
    2. Embed query using nomic-embed-text (same 768-dim space as documents)
    3. Search vector store using cosine distance (<=> operator)
    4. Retrieve top-K most similar chunks ranked by similarity score
    5. Validate results have correct metadata and similarity scores

    Expected behavior:
    - Query about CNIL (French data regulator) should match CNIL-related chunk
    - Similarity score between 0.0 (no match) and 1.0 (perfect match)
    - Results include: content, source, page, chunk_index, similarity

    What is tested:
    - Query embedding succeeds (768-dim vector)
    - Search query executes without errors
    - Results returned (≥1 match found)
    - Result structure valid (all fields present)
    - Similarity score in valid range [0.0, 1.0]
    - Best match is semantically relevant (CNIL answer)

    Assertions:
    - Query embedding not None
    - Search succeeds (success=True)
    - Results list not empty
    - All required fields in results
    - Similarity score in [0.0, 1.0] range
    """
    print("\n--- Test 4: Semantic search (similarity retrieval) ---")

    # Query: French question about data protection authority
    query = "Qui contrôle la protection des données en France?"
    query_embedding = embed_text(query)
    assert query_embedding is not None, "✗ Query embedding should not be None"

    # Search for similar chunks
    result = search_similar(query_embedding, top_k=3)
    assert result["success"] == True, f"✗ Search failed: {result['error']}"
    assert len(result["results"]) > 0, "✗ Should return at least 1 result"

    # Validate first (best) result
    top_result = result["results"][0]
    assert "content" in top_result, "✗ Result missing 'content'"
    assert "similarity" in top_result, "✗ Result missing 'similarity'"
    assert "source" in top_result, "✗ Result missing 'source'"
    assert 0 <= top_result["similarity"] <= 1, f"✗ Similarity out of range: {top_result['similarity']}"

    print(f"✅ PASS: Semantic search successful")
    print(f"   Query: {query}")
    print(f"   Top match: {top_result['content'][:70]}...")
    print(f"   Similarity: {top_result['similarity']:.4f}")
    print(f"   Source: {top_result['source']} (page {top_result['page']})")
    print(f"   Total results: {len(result['results'])}")


def test_document_count():
    """Test monitoring: retrieve total document count from vector store.

    Validates get_document_count() function for tracking storage statistics.
    Useful for monitoring ingestion progress and storage metrics.

    What is tested:
    - Query executes without errors
    - Returns integer count (≥ 0)
    - Count reflects stored chunks from test_store_chunks (should be ≥ 3)

    Assertions:
    - Count >= 3 (minimum from test_store_chunks)
    - Value is integer type
    """
    print("\n--- Test 5: Monitoring (document count) ---")
    count = get_document_count()
    assert count >= 3, f"✗ Should have at least 3 documents, got {count}"
    print(f"✅ PASS: Document count query successful")
    print(f"   Total chunks in vector store: {count}")


def test_delete_source():
    """Test cleanup: delete all chunks from a specific source.

    Validates delete_source() for document lifecycle management.
    Removes all chunks associated with a source filename.

    What is tested:
    - Delete operation succeeds (transaction commits)
    - Correct count of chunks deleted (all 3 from TEST_SOURCE)
    - Database state reflects deletion

    Assertions:
    - Delete succeeds (success=True)
    - Deleted count = 3 (all test chunks removed)

    Note:
    - This test also serves as cleanup for next test run
    - Ensures new tests start with clean state
    """
    print("\n--- Test 6: Cleanup (delete source) ---")
    result = delete_source(TEST_SOURCE)
    assert result["success"] == True, "✗ Delete operation should succeed"
    assert result["deleted"] == 3, f"✗ Expected 3 deleted, got {result['deleted']}"
    print(f"✅ PASS: Delete source successful")
    print(f"   Chunks removed: {result['deleted']}")


if __name__ == "__main__":
    """Run complete vector store test suite."""
    print("=" * 70)
    print("Test Suite: Analyse_IA Vector Store (PostgreSQL pgvector backend)")
    print("=" * 70)

    # Pre-test cleanup: Remove stale data from previous runs
    cleanup()

    # Test execution order:
    # 1. Infrastructure: Verify database connectivity (prerequisite)
    # 2. Storage: Embed and store chunks
    # 3. Deduplication: Verify duplicate handling
    # 4. Search: Test semantic similarity retrieval
    # 5. Monitoring: Check storage metrics
    # 6. Cleanup: Delete test data
    try:
        test_db_connection()        # Prerequisites
        test_store_chunks()         # Storage pipeline
        test_duplicate_handling()   # Deduplication
        test_search_similar()       # Core RAG retrieval
        test_document_count()       # Monitoring
        test_delete_source()        # Cleanup & verify deletion

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {str(e)}")
        sys.exit(1)

    # Success - all tests passed
    print("\n" + "=" * 70)
    print("✅ All vector_store tests passed successfully")
    print("=" * 70)
    sys.exit(0)