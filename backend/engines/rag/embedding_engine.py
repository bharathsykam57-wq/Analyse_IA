"""Text embedding service using sentence-transformers for semantic search.

This implementation removes external Ollama API dependency and computes embeddings
locally using Hugging Face sentence-transformers.

IMPORTANT — Embedding dimension must match the pgvector column definition (vector(384)).
Default model: all-MiniLM-L6-v2 → 384-dim, ~90 MB, fast download on Railway.
Do NOT change to paraphrase-multilingual-mpnet-base-v2 (768-dim) without also
running the corresponding Alembic migration to alter the DB column.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

# ── HuggingFace cache directory ───────────────────────────────────────────────
# On Railway / Docker, the default ~/.cache/huggingface may not be writable.
# Read HF_HOME from env (set it in Railway settings for a persistent volume),
# falling back to /tmp/huggingface so the model can at least be downloaded.
_hf_home = os.getenv("HF_HOME", os.getenv("TRANSFORMERS_CACHE", "/tmp/huggingface"))
os.makedirs(_hf_home, exist_ok=True)
os.environ.setdefault("HF_HOME", _hf_home)
os.environ.setdefault("TRANSFORMERS_CACHE", _hf_home)
# ─────────────────────────────────────────────────────────────────────────────

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# all-MiniLM-L6-v2: 384-dim, ~90 MB, fast download on Railway cold starts.
# Must stay 384-dim to match the pgvector column definition (vector(384)).
# Override via EMBED_MODEL env var — but run the Alembic migration if you change dimension.
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "8"))   # small batches to limit memory per step

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {EMBED_MODEL} (first request — may download ~90 MB)")
        _model = SentenceTransformer(EMBED_MODEL)
        logger.info(f"✓ Embedding model loaded successfully: {EMBED_MODEL}")
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
    total = len(chunks)

    for i in range(0, total, BATCH_SIZE):
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

        # Progress log every 50 chunks so Railway logs show the task is alive
        processed = i + len(batch)
        if processed % 50 == 0 or processed == total:
            logger.info(f"Embedded {processed}/{total} chunks...")

        # Short pause between batches to avoid memory buildup on CPU inference
        if i + BATCH_SIZE < total:
            time.sleep(0.1)

    success_rate = (len(embedded) / total * 100) if total else 0.0
    logger.info(
        f"✓ Embedding complete: {len(embedded)}/{total} chunks embedded "
        f"({success_rate:.1f}% success rate, {failed} failed)"
    )
    return embedded
