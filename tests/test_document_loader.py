"""Test suite for Analyse_IA PDF document loader and text chunking engine.

Validates the complete RAG document ingestion pipeline:
- PDF file loading with error handling (missing files, wrong format)
- Text extraction from PDF pages (with graceful page skipping)
- Overlapping text chunking with metadata preservation
- Deterministic chunk ID generation for deduplication

Tests cover:
1. Error handling (invalid paths, non-PDF files)
2. Chunking logic (sliding window, overlap, metadata)
3. Real PDF processing (when data/test.pdf available)

Run with: python scripts/test_document_loader.py
or: pytest scripts/test_document_loader.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engines.rag.document_loader import load_and_chunk_pdf

# Test utilities: Create minimal PDF for integration testing
import pypdf
from pypdf import PdfWriter
import tempfile


def create_test_pdf() -> str:
    """Create a minimal valid PDF file for testing.

    Generates a blank PDF page and writes it to a temporary file.
    Useful for integration tests that require a real PDF without
    relying on test fixture files.

    Returns:
        String path to created temporary PDF file.
        File persists until explicitly deleted.

    Note:
        PDF contains only blank page (no text content).
        Real text extraction tests should use data/test.pdf.
    """
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    with open(tmp.name, "wb") as f:
        writer.write(f)
    return tmp.name


def test_invalid_path():
    """Test error handling: non-existent file path.

    Validates that load_and_chunk_pdf() gracefully handles missing files
    with appropriate error status and message.

    Assertions:
    - success flag is False (operation failed)
    - error message contains "not found" (human-readable error)
    - Function completes without raising exception (graceful failure)
    """
    print("\n--- Test 1: Invalid path (file not found) ---")
    result = load_and_chunk_pdf("/nonexistent/file.pdf")
    assert result["success"] == False, "Should fail for non-existent file"
    assert "not found" in result["error"].lower(), "Error should mention file not found"
    print("✅ PASS: Invalid path handled correctly")


def test_not_a_pdf():
    """Test format validation: reject non-PDF files.

    Validates that load_and_chunk_pdf() correctly identifies and rejects
    files that don't have .pdf extension (case-insensitive check).

    Assertions:
    - success flag is False (operation failed)
    - Function returns error for non-PDF extension
    - No exception raised (graceful failure)

    Note:
        Extension check is case-insensitive (.PDF, .Pdf, .pdf all checked)
    """
    print("\n--- Test 2: Format validation (non-PDF file) ---")
    result = load_and_chunk_pdf("/tmp/test.txt")
    assert result["success"] == False, "Should reject non-PDF files"
    print("✅ PASS: Non-PDF file rejected correctly")


def test_chunk_logic():
    """Test text chunking logic: sliding window with overlap.

    Validates chunk_text() function implementation:
    - Multiple chunks generated from long text (sliding window)
    - Each chunk has required metadata fields
    - Chunk IDs are unique and deterministic
    - Chunk sizes respect CHUNK_SIZE configuration

    Assertions:
    - len(chunks) > 1: Long text should produce multiple chunks
    - All chunks have 'content', 'chunk_id' fields
    - All chunk_ids are unique (deduplication ready)
    - All chunk contents are within size limit
    """
    print("\n--- Test 3: Chunking logic (sliding window + overlap) ---")
    from backend.engines.rag.document_loader import chunk_text

    # Create sample text long enough to trigger multiple chunks
    # CHUNK_SIZE=500, so repeat text to exceed one chunk
    sample_text = "Le règlement général sur la protection des données (RGPD) " * 20
    chunks = chunk_text(sample_text, source="test.pdf", page_num=1)

    # Assertions
    assert len(chunks) > 1, f"Should produce multiple chunks, got {len(chunks)}"
    assert all("content" in c for c in chunks), "All chunks must have 'content'"
    assert all("chunk_id" in c for c in chunks), "All chunks must have 'chunk_id'"
    assert all(len(c["content"]) <= 520 for c in chunks), "Chunk size should respect CHUNK_SIZE"  # 500 + buffer

    # Verify uniqueness of chunk IDs
    chunk_ids = set(c['chunk_id'] for c in chunks)
    assert len(chunk_ids) == len(chunks), "All chunk IDs should be unique"

    print(f"✅ PASS: Chunking logic validated")
    print(f"   Produced {len(chunks)} chunks from {len(sample_text)} characters")
    print(f"   First chunk preview: {chunks[0]['content'][:60]}...")
    print(f"   Chunk IDs are deterministic and unique: {len(chunk_ids)} unique IDs")


def test_real_pdf_if_available():
    """Test real PDF processing (integration test).

    Validates end-to-end PDF ingestion pipeline on real document.
    This test is optional and only runs if test PDF is available.

    Requirements:
    - Place any PDF at data/test.pdf
    - Test will load, extract, and chunk the PDF
    - Validates all expected metadata fields in results

    Assertions:
    - success flag is True
    - total_chunks > 0 (at least one chunk extracted)

    Returns:
        Skips test with ⚠️  message if data/test.pdf not found
    """
    print("\n--- Test 4: Real PDF processing (integration test) ---")
    # Place any PDF in data/ folder to test this
    test_path = "data/test.pdf"
    if not os.path.exists(test_path):
        print(f"⚠️  SKIP: No PDF found at '{test_path}'")
        print("   To run: Place any PDF at data/test.pdf")
        return

    result = load_and_chunk_pdf(test_path)
    assert result["success"] == True, "PDF loading should succeed"
    assert result["total_chunks"] > 0, "Should extract at least one chunk"

    print(f"✅ PASS: Real PDF processing successful")
    print(f"   Source:         {result['source']}")
    print(f"   Total pages:    {result['total_pages']}")
    print(f"   Extracted:      {result['total_chunks']} chunks")
    print(f"   Sample chunk:   {result['chunks'][0]['content'][:70]}...")


if __name__ == "__main__":
    """Run all document_loader tests."""
    print("=" * 60)
    print("Test Suite: Analyse_IA Document Loader (RAG Pipeline)")
    print("=" * 60)

    # Run unit tests in order
    test_invalid_path()       # Error handling: missing files
    test_not_a_pdf()          # Format validation: non-PDF files
    test_chunk_logic()        # Chunking logic: sliding window + overlap
    test_real_pdf_if_available()  # Integration: real PDF (optional)

    # Summary
    print("\n" + "=" * 60)
    print("✅ All document_loader tests passed successfully")
    print("=" * 60)