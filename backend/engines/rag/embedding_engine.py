"""Text embedding service using sentence-transformers for semantic search.

This implementation removes external Ollama API dependency and computes embeddings
locally using Hugging Face sentence-transformers.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "32"))

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {EMBED_MODEL}")
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def check_ollama_connection() -> bool:
    """Compatibility wrapper retained for existing call sites.

    Returns True when sentence-transformers model is ready.
    """
    try:
        _get_model()
        logger.info("✓ Embedding model ready")
        return True
    except Exception as e:
        logger.error(f"✗ Embedding model initialization failed: {str(e)}", exc_info=True)
        return False


def embed_text(text: str) -> Optional[list[float]]:
    """Generate dense embedding vector for input text."""
    if not text or not text.strip():
        logger.warning("⚠ Empty text passed to embed_text — skipping")
        return None

    try:
        model = _get_model()
        embedding = model.encode(text.strip(), convert_to_numpy=True, normalize_embeddings=True)
        return embedding.astype("float32").tolist()
    except Exception as e:
        logger.error(f"✗ Embedding failed: {str(e)}", exc_info=True)
        return None


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Embed a list of text chunks in batches and return enriched chunks."""
    if not chunks:
        logger.warning("⚠ No chunks passed to embed_chunks")
        return []

    if not check_ollama_connection():
        logger.error("✗ Embedding model not available — cannot process chunks")
        return []

    model = _get_model()
    embedded: list[dict] = []
    failed = 0

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [str(chunk.get("content", "")).strip() for chunk in batch]

        try:
            vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        except Exception as e:
            logger.error(f"✗ Batch embedding failed: {str(e)}", exc_info=True)
            failed += len(batch)
            continue

        for chunk, vector in zip(batch, vectors):
            if not chunk.get("content"):
                failed += 1
                continue
            chunk_with_embedding = {**chunk, "embedding": vector.astype("float32").tolist()}
            embedded.append(chunk_with_embedding)

    success_rate = (len(embedded) / len(chunks) * 100) if chunks else 0.0
    logger.info(
        f"✓ Embedding batch complete: {len(embedded)}/{len(chunks)} chunks embedded "
        f"({success_rate:.1f}% success rate, {failed} failed)"
    )
    return embedded
