"""PDF Document Loader & Text Chunking Engine for Analyse_IA RAG Pipeline.

This module handles the complete document ingestion workflow for retrieval-augmented
generation (RAG) systems:
1. PDF file validation and text extraction (page-by-page)
2. Intelligent text chunking with configurable overlap (for semantic preservation)
3. Chunk metadata tracking (source, page number, unique IDs) for retrieval

Design principles:
- Overlapping chunks maintain semantic context across boundaries
- Deterministic chunk IDs (MD5 hashes) enable deduplication and reproducibility
- Page-by-page processing handles PDFs with corrupted pages gracefully
- Comprehensive logging provides audit trail for production debugging

Key functions:
- load_pdf(): Validate, extract, and structure PDF pages
- chunk_text(): Split page text into overlapping chunks with metadata
- load_and_chunk_pdf(): End-to-end pipeline (recommended entry point)

Usage:
    from document_loader import load_and_chunk_pdf
    result = load_and_chunk_pdf('path/to/document.pdf')
    if result['success']:
        chunks = result['chunks']  # Ready for embedding service
        print(f"Generated {result['total_chunks']} chunks")
"""

import logging
import hashlib
from pathlib import Path
from typing import Optional
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# Chunking configuration for semantic preservation in RAG pipelines
CHUNK_SIZE = 500        # Target chunk size (characters). Balance: too small=context loss, too large=slower retrieval
CHUNK_OVERLAP = 50      # Overlap between consecutive chunks (characters). Prevents semantic breaks at chunk boundaries


def load_pdf(file_path: str) -> dict:
    """Load and extract text from a PDF file page-by-page.

    Handles PDF validation, extraction error recovery, and partial success scenarios.
    Uses pypdf library for reliable cross-platform PDF parsing. Pages with extraction
    failures are logged as warnings but don't halt processing (graceful degradation).

    Extraction process:
    1. Validate file exists and has .pdf extension
    2. Initialize PdfReader from file path
    3. Iterate through pages, extract text with error handling
    4. Skip blank/failed pages; continue with remaining pages
    5. Return structured result with full metadata

    Args:
        file_path: Absolute or relative path to PDF file.
                   Accepts both pathlib.Path objects and strings.

    Returns:
        Dictionary with keys:
        - success (bool): True if ≥1 page extracted; False if file/format error
        - source (str): Original filename (without directory path)
        - file_path (str): Absolute resolved filesystem path
        - pages (list[dict]): List of successfully extracted pages:
            - page_num (int): 1-indexed page number in PDF
            - text (str): Extracted text (leading/trailing whitespace removed)
        - total_pages (int): Total page count in PDF file
        - extracted_pages (int): Count of successfully extracted pages
        - error (str|None): Error message (None if success=True)

    Raises:
        Exceptions are caught and returned as error dict (no exceptions propagated)
    """
    path = Path(file_path)

    # Validate: File must exist
    if not path.exists():
        error_msg = f"File not found: {file_path}"
        logger.error(f"✗ {error_msg}")
        return {"success": False, "error": error_msg}

    # Validate: File must be PDF (extension check)
    if path.suffix.lower() != ".pdf":
        error_msg = f"Not a PDF file: {file_path} (extension: {path.suffix})"
        logger.error(f"✗ {error_msg}")
        return {"success": False, "error": error_msg}

    try:
        # Initialize PDF reader and inspect page count
        reader = PdfReader(str(path))
        pages = []
        logger.debug(f"PDF reader initialized: {len(reader.pages)} total pages reported")

        # Extract text from each page with fault tolerance
        # Strategy: Skip corrupted/blank pages; continue with remaining pages
        for page_num, page in enumerate(reader.pages):
            try:
                # Extract text from page object (some PDFs have only scanned images)
                text = page.extract_text()
                
                # Only include pages with actual text content (skip empty/image-only pages)
                if text and text.strip():
                    pages.append({
                        "page_num": page_num + 1,  # Convert to 1-indexed for readability
                        "text": text.strip()        # Remove leading/trailing whitespace
                    })
            except Exception as e:
                # Log warning but continue - partial extraction is acceptable in RAG
                logger.warning(f"⚠ Could not extract page {page_num + 1}: {str(e)}. Skipping.")
                continue

        # Calculate and log extraction success rate
        extraction_rate = (len(pages) / len(reader.pages) * 100) if reader.pages else 0
        logger.info(
            f"✓ Loaded PDF: {path.name} | "
            f"Extracted {len(pages)}/{len(reader.pages)} pages ({extraction_rate:.0f}% success rate)"
        )

        return {
            "success": True,
            "source": path.name,
            "file_path": str(path.resolve()),
            "pages": pages,
            "total_pages": len(reader.pages),
            "extracted_pages": len(pages),
            "error": None
        }

    except Exception as e:
        error_msg = f"Failed to read PDF '{path.name}': {str(e)}"
        logger.error(f"✗ {error_msg}", exc_info=True)
        return {"success": False, "error": error_msg}


def chunk_text(text: str, source: str, page_num: int) -> list[dict]:
    """Split page text into overlapping chunks for embedding/semantic search.

    Implements a sliding-window chunking strategy to preserve semantic context
    across chunk boundaries. Each chunk includes metadata for RAG retrieval workflows
    and deduplication.

    Chunking strategy:
    - Slide window of size CHUNK_SIZE across text
    - Step forward by (CHUNK_SIZE - CHUNK_OVERLAP) to create overlaps
    - Example: CHUNK_SIZE=500, CHUNK_OVERLAP=50 means 450-char sliding step
    - Preserves contextual overlap between adjacent chunks (reduces semantic breaks)
    - Generates deterministic MD5 IDs for deduplication and cache hits

    Args:
        text: Raw extracted text from one PDF page (already trimmed)
        source: Original filename (metadata for audit trail and retrieval)
        page_num: 1-indexed page number (precise document location marker)

    Returns:
        List of chunk dictionaries (empty if input text is empty):
        Each chunk contains:
        - content (str): Chunk text (whitespace trimmed)
        - source (str): Source filename
        - page (int): Page number (1-indexed)
        - chunk_index (int): Sequential chunk number within this page [0, 1, 2, ...]
        - chunk_id (str): Deterministic MD5 hash of (source, page, chunk_index)
                         Used for deduplication across ingestion runs
    """
    # Handle empty or whitespace-only input
    if not text or not text.strip():
        return []

    chunks = []
    start = 0
    chunk_index = 0
    text = text.strip()

    # Sliding window chunking with overlap
    while start < len(text):
        # Calculate chunk boundaries
        end = start + CHUNK_SIZE
        chunk_text_content = text[start:end].strip()

        # Only add non-empty chunks (skip trailing whitespace-only chunks)
        if chunk_text_content:
            # Generate deterministic chunk ID: MD5 hash of (source_page_index)
            # Ensures reproducible IDs across multiple ingestion runs
            # Enables deduplication and reliable cache hits
            chunk_id = hashlib.md5(
                f"{source}_{page_num}_{chunk_index}".encode()
            ).hexdigest()

            chunks.append({
                "content": chunk_text_content,
                "source": source,
                "page": page_num,
                "chunk_index": chunk_index,  # Sequential position within page
                "chunk_id": chunk_id          # Unique stable identifier
            })
            chunk_index += 1

        # Slide window forward by (CHUNK_SIZE - CHUNK_OVERLAP)
        # This creates overlap between consecutive chunks, preserving context
        start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


def load_and_chunk_pdf(file_path: str) -> dict:
    """Complete ingestion pipeline: Load PDF → Extract pages → Return chunks.

    High-level entry point orchestrating the full RAG document preparation workflow.
    Combines load_pdf() and chunk_text() with error handling and production-grade
    logging for observability and debugging.

    Recommended entry point for all PDF ingestion use cases.

    Pipeline stages:
    1. Validate and load PDF file (returns early on file-level errors)
    2. For each successfully extracted page, apply sliding-window chunking
    3. Aggregate all chunks with complete metadata
    4. Return success status, chunks, and quality metrics

    Args:
        file_path: Path to PDF file (absolute or relative; pathlib.Path or str)

    Returns:
        Dictionary with keys:
        - success (bool): True if PDF loaded and ≥1 chunk generated
        - source (str): Filename (useful for logging and audit trails)
        - file_path (str): Absolute resolved file path
        - chunks (list[dict]): All chunks from all pages, each containing:
            - content: Chunk text
            - source: Source filename
            - page: 1-indexed page number
            - chunk_index: Sequential position within page
            - chunk_id: Unique deterministic identifier
        - total_chunks (int): Total chunks across all pages
        - total_pages (int): Total pages in PDF file
        - error (str|None): Error message (None if success=True)

    Example:
        >>> result = load_and_chunk_pdf('document.pdf')
        >>> if result['success']:
        ...     print(f"{result['total_chunks']} chunks ready for embedding")
        ...     for chunk in result['chunks'][:3]:
        ...         print(f"  Page {chunk['page']}, chunk {chunk['chunk_index']}")
    """
    # Stage 1: Load PDF with validation (short-circuit on failure)
    pdf_result = load_pdf(file_path)

    if not pdf_result["success"]:
        # Propagate file-level errors (not found, wrong format, read failure)
        logger.error(f"✗ Pipeline aborted: PDF loading failed")
        return pdf_result

    # Stage 2: Generate chunks from all extracted pages
    all_chunks = []

    for page in pdf_result["pages"]:
        # Apply sliding-window chunking to each page
        page_chunks = chunk_text(
            text=page["text"],
            source=pdf_result["source"],
            page_num=page["page_num"]
        )
        all_chunks.extend(page_chunks)

    # Summary: Transformation metrics (pages → chunks)
    # Calculate average chunks per page for quality metrics
    avg_chunks_per_page = len(all_chunks) / (pdf_result['extracted_pages'] or 1)
    logger.info(
        f"✓ RAG pipeline complete: {pdf_result['source']} | "
        f"{pdf_result['extracted_pages']} pages → {len(all_chunks)} chunks | "
        f"Avg {avg_chunks_per_page:.1f} chunks/page"
    )

    return {
        "success": True,
        "source": pdf_result["source"],
        "file_path": pdf_result["file_path"],
        "chunks": all_chunks,              # List of chunks ready for embedding service
        "total_chunks": len(all_chunks),
        "total_pages": pdf_result["total_pages"],
        "error": None
    }