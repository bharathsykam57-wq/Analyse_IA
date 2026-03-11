"""Text embedding service using nomic-embed-text model via Ollama.

Converts text chunks into dense 768-dimensional vector embeddings suitable
for semantic search and similarity matching in pgvector databases.

Architecture:
- Uses Ollama local inference server for privacy-preserving embeddings
- Model: nomic-embed-text (768 dims, fast, high-quality)
- Batch processing: Processes chunks in configurable batches to manage memory
- Error resilience: Skips failed chunks, continues processing remaining

Pipeline integration:
- Input: Text chunks from document_loader (with metadata)
- Process: Convert text → 768-dim vectors via Ollama API
- Output: Chunks with 'embedding' field for pgvector storage

Configuration:
- OLLAMA_URL: Local Ollama server endpoint (port 11434)
- EMBED_MODEL: Model name ("nomic-embed-text")
- BATCH_SIZE: Chunks per request (10 recommended for 8GB+ RAM)

Dependencies:
- Ollama running locally: ollama serve
- Model pulled: ollama pull nomic-embed-text

Usage:
    from embedding_engine import check_ollama_connection, embed_chunks
    if check_ollama_connection():
        embedded = embed_chunks(chunks)  # chunks have 'embedding' field added
"""

import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration: Ollama connection settings
OLLAMA_URL = "http://localhost:11434"          # Local Ollama API endpoint
EMBED_MODEL = "nomic-embed-text"               # Model name (768-dim embeddings)
BATCH_SIZE = 10                                # Chunks per batch (tune based on available RAM)


def check_ollama_connection() -> bool:
    """Verify Ollama is running and nomic-embed-text model is available.

    Pre-flight health check before attempting embeddings. Validates:
    1. Ollama server responds at OLLAMA_URL:11434
    2. nomic-embed-text model is pulled and available
    3. API endpoints are responding correctly

    This should be called before embedding operations to fail fast with
    clear error messages if dependencies are missing.

    Returns:
        bool: True if Ollama is ready for embeddings, False otherwise

    Logs:
        - INFO: Connection successful with model available
        - ERROR: Connection failure, missing model, or API issues
        - Hints provided for common problems (e.g., "ollama pull ...")
    """
    try:
        # Step 1: Check Ollama API is responding
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code != 200:
            logger.error(f"✗ Ollama not responding correctly (HTTP {response.status_code})")
            return False

        # Step 2: Extract available models and check for EMBED_MODEL
        models = [m["name"] for m in response.json().get("models", [])]
        available = any(EMBED_MODEL in m for m in models)

        if not available:
            logger.error(
                f"✗ Model '{EMBED_MODEL}' not found in Ollama. "
                f"Pull it with: ollama pull {EMBED_MODEL}"
            )
            return False

        # Step 3: Success - log available models for debugging
        logger.info(f"✓ Ollama connection OK — {len(models)} models available, {EMBED_MODEL} ready")
        return True

    except requests.exceptions.ConnectionError:
        logger.error(
            f"✗ Cannot connect to Ollama at {OLLAMA_URL}. "
            f"Is it running? Start with: ollama serve"
        )
        return False
    except Exception as e:
        logger.error(f"✗ Ollama health check failed: {str(e)}", exc_info=True)
        return False


def embed_text(text: str) -> Optional[list[float]]:
    """Generate a 768-dimensional embedding vector for input text.

    Sends text to Ollama's embedding API (nomic-embed-text model) and
    returns the resulting vector. Used for both single-text and batch
    embedding operations.

    Model properties:
    - Output: 768-dimensional vector (float32)
    - Pooling: Mean pooling over token embeddings
    - Context: Supports up to 2048 tokens per text
    - Speed: ~100ms latency per request over localhost

    Args:
        text (str): Input text to embed. Can be single word or long document.
                   Whitespace is stripped before sending to Ollama.

    Returns:
        Optional[list[float]]: List of 768 floats if successful, None if:
                              - Input text is empty/whitespace
                              - API request fails (connection, timeout)
                              - Ollama returns invalid response
                              - No embedding in response

    Raises:
        Does not raise exceptions; logs errors and returns None for graceful
        degradation in batch processing.

    Example:
        >>> embedding = embed_text("What is machine learning?")
        >>> len(embedding)
        768
        >>> type(embedding[0])
        <class 'float'>
    """
    # Handle empty input
    if not text or not text.strip():
        logger.warning("⚠ Empty text passed to embed_text — skipping")
        return None

    try:
        # POST to Ollama embedding endpoint
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text.strip()},
            timeout=30  # 30s timeout for embedding generation
        )

        # Check HTTP response status
        if response.status_code != 200:
            logger.error(f"✗ Embedding API error: HTTP {response.status_code}")
            logger.debug(f"  Response: {response.text[:200]}")  # Log first 200 chars
            return None

        # Extract embedding from response JSON
        embedding = response.json().get("embedding")

        if not embedding:
            logger.error("✗ No embedding in Ollama response (empty array)")
            return None

        # Validate embedding dimensionality
        if len(embedding) != 768:
            logger.warning(f"⚠ Unexpected embedding dimension: {len(embedding)} (expected 768)")

        return embedding

    except requests.exceptions.Timeout:
        logger.error("✗ Embedding request timed out (30s limit exceeded)")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"✗ Cannot connect to Ollama at {OLLAMA_URL}")
        return None
    except Exception as e:
        logger.error(f"✗ Embedding failed: {str(e)}", exc_info=True)
        return None


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Embed a list of text chunks in batches for efficient processing.

    Main entry point for batch embedding of document chunks. Processes chunks
    in configurable batches (BATCH_SIZE) to balance memory usage and latency.
    Embeds each chunk independently and adds 'embedding' field to result.

    Batch processing strategy:
    - Divides chunks into BATCH_SIZE batches (e.g., 10 chunks per batch)
    - Processes batches sequentially to monitor memory/CPU
    - Skips failed embeddings with warning (graceful degradation)
    - Returns partial results if some chunks fail

    Input chunks expected format:
        {
            'content': 'text to embed',
            'chunk_id': 'unique_id',
            'source': 'filename',
            'page': 1,
            ... (other metadata preserved)
        }

    Output chunks add:
        'embedding': list[float] with 768 values

    Args:
        chunks (list[dict]): List of chunk dicts with 'content' key.
                            Each chunk should have metadata (source, page, chunk_id).

    Returns:
        list[dict]: Chunks with 'embedding' field added. Original metadata preserved.
                   Failed chunks are excluded (not included in output).
                   Empty list if no chunks successfully embedded.

    Logs:
        - Progress: Batch X/Y with count and timestamp
        - Failures: Chunk ID and reason for skipped chunks
        - Summary: Total embedded, failed count, success rate

    Example:
        >>> chunks = [{'content': 'text1', 'chunk_id': '123'},
        ...           {'content': 'text2', 'chunk_id': '456'}]
        >>> result = embed_chunks(chunks)
        >>> len(result[0]['embedding'])
        768
    """
    # Input validation
    if not chunks:
        logger.warning("⚠ No chunks passed to embed_chunks")
        return []

    # Pre-flight check: Ensure Ollama is ready
    if not check_ollama_connection():
        logger.error("✗ Ollama not available — cannot process chunks")
        return []

    embedded = []
    total = len(chunks)
    failed = 0

    # Batch processing loop
    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(f"◈ Embedding batch {batch_num}/{total_batches} ({len(batch)} chunks)")

        # Embed each chunk in the batch
        for chunk in batch:
            content = chunk.get("content", "")
            chunk_id = chunk.get("chunk_id", "?")
            
            # Generate embedding vector
            embedding = embed_text(content)

            if embedding is None:
                # Embedding failed - log and skip
                logger.warning(f"  → Skipping chunk {chunk_id}: embedding generation failed")
                failed += 1
                continue

            # Add embedding to chunk and collect result
            chunk_with_embedding = {**chunk, "embedding": embedding}
            embedded.append(chunk_with_embedding)

    # Summary statistics
    success_rate = (len(embedded) / total * 100) if total > 0 else 0
    logger.info(
        f"✓ Embedding batch complete: {len(embedded)}/{total} chunks embedded "
        f"({success_rate:.1f}% success rate, {failed} failed)"
    )

    return embedded