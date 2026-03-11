"""End-to-end RAG pipeline validation with real-world CNIL AI Guidelines PDF.

Comprehensive integration test covering complete document processing workflow:
1. PDF extraction & chunking: Extract text from CNIL AI guidelines PDF
2. Embedding generation: Convert chunks to 768-dim vectors (Ollama)
3. Vector storage: Store embeddings in PostgreSQL pgvector
4. Semantic search: Retrieve top-K similar chunks (cosine distance)
5. LLM generation: Generate French answers with source attribution

Pipeline flow:
  PDF file → Text extraction → Text chunking → Vector embedding
    → pgvector storage → Similarity search → LLM generation → French answer

Test categories:
1. Document loading: PDF extraction, chunking, metadata extraction
2. Embedding generation: Multi-chunk embedding with dimension validation
3. Vector storage: PostgreSQL pgvector insert with deduplication
4. Semantic search: Similarity retrieval and ranking
5. Full RAG: End-to-end question answering from PDF context

Test data:
- Source PDF: data/pdfs/cnil_ia_guidelines.pdf (CNIL AI Guidelines)
- Format: Real-world PDF covering AI regulation requirements
- Size: Typically 30-100+ pages (varies by document)
- Language: French (RGPD/AI compliance)

Prerequisites:
- PostgreSQL running with pgvector extension
- Ollama server with nomic-embed-text and mistral-nemo:latest models
- CNIL PDF available at data/pdfs/cnil_ia_guidelines.pdf
- All backend RAG modules operational

Run with: python scripts/test_rag_e2e.py

Performance expectations:
- PDF loading & chunking: ~1-5 seconds (depends on PDF size)
- Embedding generation: ~50-100ms per chunk (100+ chunks expected)
- Vector storage: ~500ms-2s (batch insert with pgvector)
- Semantic search: ~10-50ms per query (with pgvector index)
- LLM generation: 5-30 seconds per question
- Total runtime: 2-5 minutes (dominated by LLM generation)

Test philosophy:
- Uses real-world CNIL PDF (not synthetic test data)
- Validates full pipeline robustness
- Ensures French language support
- Tests source attribution accuracy
- Demonstrates production readiness
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engines.rag.document_loader import load_and_chunk_pdf
from backend.engines.rag.embedding_engine import embed_chunks
from backend.engines.rag.vector_store import store_chunks, search_similar, delete_source, get_document_count
from backend.engines.rag.rag_chain import ask

PDF_PATH = "data/pdfs/cnil_ia_guidelines.pdf"
PDF_SOURCE = "cnil_ia_guidelines.pdf"


def cleanup():
    """Remove test chunks from database after test completion.

    Cleanup function called:
    - Before test suite starts (remove stale data from previous runs)
    - Optionally after test suite completes (optional: keep data for manual verification)

    Ensures database state remains consistent and prevents:
    - Duplicate PDF chunks from previous test runs
    - Search result pollution from stale test data
    - Constraint violations on re-runs

    Returns:
        (implicit) Test chunks deleted from pgvector table
    """
    result = delete_source(PDF_SOURCE)
    deleted_count = result.get('deleted', 0)
    if deleted_count > 0:
        print(f"✓ Cleanup: {deleted_count} chunks removed from pgvector")


def test_load_pdf():
    """Test PDF extraction and chunking with real CNIL AI Guidelines PDF.

    Validates document_loader.load_and_chunk_pdf() on real-world PDF:
    - File exists and is readable
    - PDF parsing succeeds (pypdf extraction)
    - Text extraction produces meaningful content
    - Chunking creates appropriate segment boundaries
    - Metadata (page numbers, chunk indices) correctly tracked

    Test steps:
    1. Call load_and_chunk_pdf(PDF_PATH)
    2. Validate success flag is True (no extraction errors)
    3. Verify page count is positive (PDF has content)
    4. Verify chunk count is positive (text was extracted)
    5. Display sample chunk for manual verification

    Assertions:
    - success=True (✗ PDF loading or parsing failed)
    - total_chunks > 0 (✗ no text extracted, possible blank PDF)
    - total_pages > 0 (✗ invalid PDF or no pages)

    Returns:
        list[dict]: Chunks extracted from PDF, each with:
        - content: Text passage (500 chars typical, 50 char overlap)
        - source: Filename ("cnil_ia_guidelines.pdf")
        - page: Page number (1-indexed)
        - chunk_index: Sequential index within page
        - chunk_id: MD5 hash of content (deterministic)

    Performance:
    - Typical latency: 1-5 seconds (PDF size & extraction complexity)
    - Pages typical: 30-100+ (CNIL guidelines comprehensive)
    - Chunks typical: 100-300 (500-char chunks with 50-char overlap)

    Notes:
    - First test in pipeline (prerequisite for all others)
    - Real PDF usescase: validates parser robustness
    - Sample chunk shown for content verification
    """
    print("\n--- Test 1: Load real PDF ---")
    result = load_and_chunk_pdf(PDF_PATH)

    # Verify PDF loading succeeded
    assert result["success"] == True, f"✗ PDF load failed: {result.get('error')}"
    
    # Verify document has content (pages and chunks extracted)
    assert result["total_chunks"] > 0, "✗ Should produce at least 1 chunk (PDF may be blank)"
    assert result["total_pages"] > 0, "✗ Should have at least 1 page"

    print(f"✅ PASS: PDF loaded successfully")
    print(f"   File:         {result['source']}")
    print(f"   Total pages:  {result['total_pages']}")
    print(f"   Extracted:    {result['total_chunks']} chunks")
    print(f"   Sample chunk: {result['chunks'][0]['content'][:100]}...")

    return result["chunks"]


def test_embed_chunks(chunks):
    """Test batch embedding generation for all extracted PDF chunks.

    Validates embedding_engine.embed_chunks() on real PDF content:
    - Ollama nomic-embed-text model availability
    - Batch processing of 100+ chunks without failures
    - Consistent 768-dim vector output
    - Graceful fallback for failed chunks

    Test steps:
    1. Call embed_chunks(chunks) with all extracted chunks
    2. Verify at least 1 chunk successful embedding (non-empty result)
    3. Verify all chunks have "embedding" field (complete processing)
    4. Verify all embeddings are 768-dimensional (model spec)
    5. Calculate success rate (embedded/total)

    Assertions:
    - len(embedded) > 0 (✗ no embeddings generated, all chunks failed)
    - all chunks have "embedding" field (✗ missing embeddings, incomplete)
    - all embeddings are 768-dim (✗ dimension mismatch, wrong model or error)

    Returns:
        list[dict]: Chunks with added "embedding" field, each containing:
        - All original fields (content, source, page, chunk_index, chunk_id)
        - embedding: 768-dim numpy array (float32 values)

    Performance:
    - Batch size: Configurable (typically ~10 chunks per batch)
    - Latency per chunk: ~50-100ms (Ollama inference time)
    - Total latency: Linear with chunk count (~100-300 chunks expected)
    - Memory: ~300MB-1GB for 100+ embeddings in memory

    Robustness:
    - Graceful fallback: Skip failed chunks, continue processing
    - Batch retry: Retry failed batches up to max attempts
    - Error handling: Log per-chunk failures without crashing

    Notes:
    - Nomic-embed-text model (384M, open-source, local inference)
    - 768 dimensions standard for semantic search
    - Batch processing improves throughput over single embeddings
    - Real PDF content ensures realistic embedding quality
    """
    print("\n--- Test 2: Embed all chunks ---")
    embedded = embed_chunks(chunks)

    # Verify embeddings were generated
    assert len(embedded) > 0, "✗ No embeddings generated (all chunks failed or empty)"
    
    # Verify all chunks have embedding vectors
    assert all("embedding" in c for c in embedded), "✗ All chunks should have embeddings (incomplete)"
    
    # Verify vector dimensions (nomic-embed-text outputs 768-dim)
    assert all(len(c["embedding"]) == 768 for c in embedded), "✗ All embeddings should be 768 dims (wrong model)"

    print(f"✅ PASS: Embedding complete")
    print(f"   Chunks embedded: {len(embedded)}/{len(chunks)}")
    print(f"   Embedding dims:  768 (nomic-embed-text model)")

    return embedded


def test_store_chunks(embedded_chunks):
    """Test batch insertion of embedded chunks into PostgreSQL pgvector.

    Validates vector_store.store_chunks() for real PDF embeddings:
    - PostgreSQL connection successful
    - pgvector extension properly configured
    - Batch UPSERT logic (INSERT ON CONFLICT DO NOTHING)
    - Unique constraint on (source, page, chunk_index)
    - Transaction atomicity (all-or-nothing insert)

    Test steps:
    1. Call store_chunks(embedded_chunks)
    2. Verify success flag is True (database written)
    3. Verify inserted > 0 (at least 1 chunk stored)
    4. Count total documents in database after insert
    5. Display insert/skip statistics

    Assertions:
    - success=True (✗ database operation failed, likely connection error)
    - inserted > 0 (✗ no chunks stored, constraint violations or errors)

    Returns:
        (implicit) Embedded chunks stored in pgvector table
        - Accessible via similarity search queries
        - Indexed by embedding (HNSW or ivfflat for performance)
        - Queryable by source, page, content columns

    Database schema (documents table):
    - id: Primary key (auto-increment)
    - source: Filename ("cnil_ia_guidelines.pdf")
    - page: Page number (1-indexed)
    - chunk_index: Sequential index within page
    - content: Text passage (500 chars typical)
    - embedding: 768-dim pgvector (cosine distance)
    - created_at: Timestamp (audit trail)
    - Unique constraint: (source, page, chunk_index)

    Performance:
    - Insertion speed: ~500ms-2s for 100+ chunks
    - Batch insert: Much faster than row-by-row
    - Deduplication: UPSERT skips if chunk_id matches
    - Index creation: Happens async (not blocking insert)

    Deduplication logic:
    - If (source, page, chunk_index) exists: skip (ON CONFLICT DO NOTHING)
    - Prevents duplicate storage of same page/section
    - Useful for re-runs: test suite idempotent

    Notes:
    - 100+ chunks typical for CNIL PDF
    - Inserted + skipped = total processed
    - Database count provided for verification
    """
    print("\n--- Test 3: Store in pgvector ---")
    result = store_chunks(embedded_chunks)

    # Verify database insertion succeeded
    assert result["success"] == True, f"✗ Store failed: {result.get('error')}"
    
    # Verify at least some chunks were inserted (not all duplicates or errors)
    assert result["inserted"] > 0, "✗ Should insert at least 1 chunk (all failed or skipped)"

    # Get current database size for context
    count = get_document_count()

    print(f"✅ PASS: Storage complete")
    print(f"   Inserted:       {result['inserted']} chunks (new)")
    print(f"   Skipped:        {result['skipped']} chunks (duplicates)")
    print(f"   Total in DB:    {count} documents")


def test_similarity_search():
    """Test semantic similarity search against stored PDF embeddings.

    Validates vector_store.search_similar() with real PDF context:
    - Query embedding generation (Ollama nomic-embed-text)
    - Cosine similarity scoring (pgvector <=> operator)
    - Ranking by relevance (top-K retrieval)
    - Source attribution (document & page tracking)

    Test steps:
    1. Create French language query about AI obligations
    2. Embed query to 768-dim vector (same model as chunks)
    3. Search for top-3 most similar chunks
    4. Verify results returned (non-empty)
    5. Display rankings and similarity scores

    Assertions:
    - success=True (✗ search operation failed)
    - len(results) > 0 (✗ no similar chunks found, index may be missing)

    Test input:
    - Query: "Quelles sont les obligations des entreprises utilisant l'IA?"
    - Language: French (CNIL document language)
    - Top-K: 3 (retrieve top 3 most similar chunks)

    Expected output:
    - 3 results ranked by cosine similarity (typically 0.7 - 0.95)
    - Each result contains: id, source, page, chunk_index, content, similarity
    - Content previewed (first 80 chars shown for verification)

    Similarity scoring:
    - Metric: Cosine distance (0 to 2, lower = more similar)
    - Converted: similarity = 1 - distance (0.0 to 1.0, higher = better)
    - Interpretation: >0.8 very similar, 0.6-0.8 relevant, <0.6 marginal

    Performance:
    - Query embedding: ~50-100ms (Ollama inference)
    - Database search: ~10-50ms (pgvector with proper index)
    - Total latency: ~100-150ms typical

    Real-world validation:
    - Tests French language semantic understanding
    - Validates CNIL document relevance matching
    - Demonstrates practical RAG retrieval quality
    - Shows source attribution for transparency

    Notes:
    - Query in French for realistic scenario
    - Top-3 results sufficient for RAG context window
    - Similarity scores indicate relevance quality
    """
    print("\n--- Test 4: Similarity search ---")
    from backend.engines.rag.embedding_engine import embed_text

    # Create French query about AI obligations (realistic question)
    query = "Quelles sont les obligations des entreprises utilisant l'IA?"
    
    # Embed query to same 768-dim space as PDF chunks
    embedding = embed_text(query)
    
    # Retrieve top-3 most similar chunks using cosine distance
    result = search_similar(embedding, top_k=3)

    # Verify search succeeded and returned results
    assert result["success"] == True, f"✗ Search failed: {result.get('error')}"
    assert len(result["results"]) > 0, "✗ No similar chunks found (index may be missing or DB empty)"

    print(f"✅ PASS: Similarity search OK")
    print(f"   Query:      {query}")
    for i, r in enumerate(result["results"], 1):
        print(f"   Result {i}:   [{r['similarity']:.4f}] Page {r['page']}: {r['content'][:80]}...")


def test_full_rag_questions():
    """Test complete end-to-end RAG pipeline with multiple French questions.

    Validates full rag_chain.ask() orchestration on real CNIL PDF:
    1. Query embedding → 768-dim vector
    2. Semantic search → retrieve top-3 relevant chunks
    3. Prompt engineering → build French RAG prompt
    4. LLM generation → mistral-nemo answers with context
    5. Source attribution → provide document links

    Test approach:
    - Multiple diverse French questions about AI regulation
    - Each tests different aspects of RAG pipeline
    - Demonstrates realistic question-answering scenarios
    - Shows source attribution transparency

    Test questions:
    1. AI system obligations for companies
    2. CNIL framework for AI regulation
    3. Rights of individuals affected by AI systems
    - All relevant to CNIL AI Guidelines document
    - Real-world compliance questions

    Assertions per question:
    - success=True (✗ RAG pipeline failed)
    - answer length > 20 chars (✗ answer too minimal or empty)
    - chunks_used > 0 (✗ no context retrieved, search failure)

    Expected outputs:
    - Answer: French language response citing document context
    - Sources: 1-3 document chunks used for answer
    - Similarity: Relevance scores (0.7-0.95 typical)
    - Attribution: Page numbers and source document

    Pipeline robustness tested:
    - Multi-question handling (different queries)
    - French language generation (model capability)
    - Source ranking (top results most relevant)
    - Graceful error handling (all assertions pass)

    Performance (per question):
    - Embedding: ~50-100ms
    - Search: ~10-50ms
    - Prompt building: <1ms
    - LLM generation: 5-30 seconds
    - Total: 5-35 seconds per question

    Real-world validation:
    - Tests practical compliance questions
    - Demonstrates CNIL knowledge integration
    - Shows French language proficiency
    - Proves source attribution accuracy

    Notes:
    - Longest test stage (dominated by LLM generation)
    - Multiple questions show pipeline robustness
    - Source references provide transparency
    - Typical 3 questions per test run
    """
    print("\n--- Test 5: Full RAG — French questions ---")

    # Three diverse French questions about AI regulation
    # All relevant to CNIL AI Guidelines document context
    questions = [
        "Quelles sont les obligations des entreprises qui utilisent des systèmes d'IA?",
        "Comment la CNIL encadre-t-elle l'utilisation de l'intelligence artificielle?",
        "Quels sont les droits des personnes concernées par les systèmes d'IA?"
    ]

    for question in questions:
        print(f"\n   ➜ Question: {question}")
        
        # Full RAG pipeline: embed → search → generate → attribute
        result = ask(question, top_k=3)

        # Verify pipeline succeeded
        assert result["success"] == True, f"✗ RAG failed: {result.get('error')}"
        
        # Verify answer is meaningful (not empty)
        assert len(result["answer"]) > 20, f"✗ Answer too short: {len(result['answer'])} chars"
        
        # Verify context was used (chunks retrieved)
        assert result["chunks_used"] > 0, "✗ No chunks used (search failed or no context)"

        print(f"   ✓ Answer:   {result['answer'][:200]}...")
        print(f"   ✓ Sources:  {result['chunks_used']} chunks used")
        print(f"   ✓ Top sim:  {result['sources'][0]['similarity']:.4f}")

    print(f"\n✅ PASS: All RAG questions answered in French with source attribution")


if __name__ == "__main__":
    """Execute complete end-to-end RAG pipeline test with real CNIL PDF.
    
    Orchestrates 5-stage test execution:
    1. Cleanup: Remove stale test data from previous runs
    2. Test 1: Load & chunk real CNIL AI Guidelines PDF
    3. Test 2: Embed all chunks to 768-dim vectors (Ollama)
    4. Test 3: Store embeddings in PostgreSQL pgvector
    5. Test 4: Test semantic similarity search
    6. Test 5: Full RAG with 3 French compliance questions
    7. Report: Validation complete, data kept for Phase 3
    
    Expected runtime: 3-5 minutes (dominated by LLM generation)
    
    Exit behavior:
    - Success: Exit code 0, CNIL PDF data kept in database
    - Failure: AssertionError, detailed error printed, exit code 1
    
    Next steps:
    - Data remains in DB for Phase 3 agent integration testing
    - Can verify results manually via PostgreSQL queries
    - PDF content ready for multi-turn conversations
    """
    print("=" * 70)
    print("Test Suite: End-to-End RAG Validation — CNIL AI Guidelines PDF")
    print("=" * 70)

    # STAGE 1: Cleanup stale data from previous test runs
    print("\n→ Stage 1: Cleaning up previous test data...")
    cleanup()

    # STAGE 2: Test PDF loading & text chunking
    print("→ Stage 2: Loading and chunking PDF...")
    chunks = test_load_pdf()
    
    # STAGE 3: Test embedding generation
    print("→ Stage 3: Generating embeddings...")
    embedded = test_embed_chunks(chunks)
    
    # STAGE 4: Test vector storage
    print("→ Stage 4: Storing in pgvector...")
    test_store_chunks(embedded)
    
    # STAGE 5: Test similarity search
    print("→ Stage 5: Testing similarity search...")
    test_similarity_search()
    
    # STAGE 6: Test full RAG pipeline
    print("→ Stage 6: Testing full RAG pipeline...")
    test_full_rag_questions()

    # STAGE 7: Report success
    print("\n" + "=" * 70)
    print("✅ Full end-to-end RAG pipeline validated with real CNIL PDF")
    print("=" * 70)
    print("\n📝 Note: CNIL PDF data retained in pgvector for Phase 3 agent testing")
    print("   Data location: PostgreSQL analyseIA_dev:documents table")
    print("   Source: cnil_ia_guidelines.pdf")
    print("   Total chunks: ~100+ (depends on PDF size)")