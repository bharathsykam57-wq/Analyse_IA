"""RAG Vector Store: PostgreSQL pgvector backend for semantic search.

Provides semantic vector storage and retrieval for Analyse_IA RAG pipeline.
Manages dense vector embeddings for document chunks with efficient similarity search.

Architecture:
- Storage: PostgreSQL with pgvector extension (768-dim vectors)
- Index: Similarity search using operators (<=> cosine distance, <#> L2 distance)
- Deduplication: UPSERT logic prevents storing duplicate chunks
- Scalability: Batch inserts, configurable connection pooling

Tables:
- documents: Stores embedded chunks with metadata
  Columns: id, source, page, chunk_index, content, embedding, created_at

Key operations:
1. store_chunks(): Batch insert embedded chunks with deduplication
2. search_similar(): Find top-K most similar chunks to query vector
3. delete_source(): Remove all chunks from a document
4. get_document_count(): Retrieve total stored chunks

Database configuration:
- Host, port, database, user (from environment variables or defaults)
- Connection via psycopg2 with automatic pooling
- pgvector extension required (CREATE EXTENSION IF NOT EXISTS vector)

Usage:
    from vector_store import store_chunks, search_similar
    # After embedding: store_chunks(embedded_chunks)
    # For search: results = search_similar(query_embedding, top_k=5)
"""

import logging
import os
from typing import Optional
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# PostgreSQL connection configuration (from environment or defaults)
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "analyseIA_dev"),          # Database name
    "user": os.getenv("DB_USER", "sykambharath"),              # Database user
    "password": os.getenv("DB_PASSWORD", ""),                  # Authentication
    "host": os.getenv("DB_HOST", "localhost"),                 # Server address
    "port": os.getenv("DB_PORT", "5432"),                      # Port (pgvector default)
}


def get_connection():
    """Create and return a PostgreSQL database connection.

    Establishes connection to vector store (pgvector-enabled PostgreSQL).
    Connection is short-lived and should be closed after use (context manager recommended).

    Connection details from DB_CONFIG:
    - Database: analyseIA_dev (or DB_NAME env var)
    - User: sykambharath (or DB_USER env var)
    - Host: localhost (or DB_HOST env var)
    - Port: 5432 (or DB_PORT env var)

    Returns:
        psycopg2 connection object if successful, None if connection failed
        Caller is responsible for closing connection (use with context manager)

    Logs:
        - ERROR: On connection failure with exception details

    Example:
        >>> conn = get_connection()
        >>> with conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT COUNT(*) FROM documents")
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.debug(f"✓ Database connection established to {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"✗ Database connection failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"✗ Unexpected connection error: {str(e)}", exc_info=True)
        return None


def store_chunks(embedded_chunks: list[dict]) -> dict:
    """Batch insert embedded chunks into vector store with deduplication.

    Main entry point for storing embeddings in PostgreSQL pgvector table.
    Uses UPSERT (INSERT ON CONFLICT DO NOTHING) to skip duplicate chunks
    identified by unique constraint on (source, page, chunk_index).

    Process:
    1. Validate input (non-empty list)
    2. Establish database connection
    3. For each chunk: Insert or skip if duplicate
    4. Commit transaction atomically
    5. Report success, inserted count, skipped count

    Input chunks expected format:
        {
            'content': 'text content',
            'source': 'filename.pdf',
            'page': 1,
            'chunk_index': 0,
            'embedding': [768 floats],
            ... (other metadata)
        }

    Args:
        embedded_chunks (list[dict]): Chunks from embed_chunks() with 'embedding' field.
                                     Each chunk must have: content, source, page, chunk_index, embedding

    Returns:
        dict with keys:
        - success (bool): True if transaction completed (even if all skipped)
        - inserted (int): Number of new chunks stored
        - skipped (int): Number of duplicate chunks (not reinserted)
        - error (str|None): Error message if success=False

    Logs:
        - WARNING: Per-chunk failures (continues processing)
        - INFO: Summary (total inserted/skipped)
        - ERROR: Transaction-level failures

    Example:
        >>> result = store_chunks(embedded_chunks)
        >>> if result['success']:
        ...     print(f"Stored {result['inserted']} chunks")

    Note:
        - Duplicate detection based on unique (source, page, chunk_index)
        - Embeddings stored as 768-dim pgvector type (text serialized)
        - Transaction is atomic (all-or-nothing)
    """
    if not embedded_chunks:
        logger.warning("⚠ No chunks to store (empty list)")
        return {"success": False, "error": "No chunks provided", "inserted": 0, "skipped": 0}

    conn = get_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed", "inserted": 0, "skipped": 0}

    inserted = 0
    skipped = 0

    try:
        with conn:  # Atomic transaction
            with conn.cursor() as cur:
                for chunk in embedded_chunks:
                    try:
                        # UPSERT logic: insert or skip if (source, page, chunk_index) duplicate
                        cur.execute("""
                            INSERT INTO documents
                                (source, page, chunk_index, content, embedding)
                            VALUES (%s, %s, %s, %s, %s::vector)
                            ON CONFLICT (source, page, chunk_index) DO NOTHING
                        """, (
                            chunk.get("source", "unknown"),
                            chunk.get("page", 0),
                            chunk.get("chunk_index", 0),
                            chunk.get("content", ""),
                            str(chunk.get("embedding", []))
                        ))

                        if cur.rowcount > 0:
                            inserted += 1
                        else:
                            skipped += 1

                    except Exception as e:
                        logger.warning(f"  → Chunk {chunk.get('chunk_id', '?')}: Insert failed ({str(e)})")
                        skipped += 1
                        continue

        logger.info(f"✓ Store complete: {inserted} inserted, {skipped} skipped (duplicates)")

        return {
            "success": True,
            "inserted": inserted,
            "skipped": skipped,
            "error": None
        }

    except Exception as e:
        logger.error(f"✗ store_chunks failed: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e), "inserted": inserted, "skipped": skipped}

    finally:
        conn.close()


def search_similar(query_embedding: list[float], top_k: int = 5) -> dict:
    """
    Find the most similar chunks to a query embedding using cosine similarity.

    Args:
        query_embedding: 768-dim float vector from embed_text()
        top_k: number of results to return (default 5)

    Returns:
        dict with success, results (list of dicts), error
    """
    if not query_embedding:
        return {"success": False, "error": "No query embedding provided"}

    conn = get_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        from pgvector.psycopg2 import register_vector
        import numpy as np
        register_vector(conn)

        embedding_array = np.array(query_embedding, dtype=np.float32)
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                source,
                page,
                chunk_index,
                content,
                1 - (embedding <=> %s) AS similarity
            FROM documents
            ORDER BY embedding <=> %s
            LIMIT %s
        """, (embedding_array, embedding_array, top_k))

        rows = cur.fetchall()
        cur.close()

        results = [
            {
                "id": row[0],
                "source": row[1],
                "page": row[2],
                "chunk_index": row[3],
                "content": row[4],
                "similarity": round(float(row[5]), 4)
            }
            for row in rows
        ]

        logger.info(f"Search returned {len(results)}/{top_k} results")

        return {
            "success": True,
            "results": results,
            "total": len(results),
            "error": None
        }

    except Exception as e:
        logger.error(f"search_similar failed: {e}")
        return {"success": False, "error": str(e)}

    finally:
        conn.close()


def get_document_count() -> int:
    """Get total number of chunks stored in the vector store.

    Returns count of all documents in the vector store database table.
    Useful for monitoring ingestion progress and storage statistics.

    Returns:
        int: Total chunk count (≥ 0). Returns 0 on connection error.

    Logs:
        - ERROR: On query failure

    Example:
        >>> count = get_document_count()
        >>> print(f"Vector store contains {count} chunks")
    """
    conn = get_connection()
    if not conn:
        logger.warning("⚠ Cannot get document count (connection failed)")
        return 0

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM documents")
                count = cur.fetchone()[0]
                logger.debug(f"Document count: {count}")
                return count
    except Exception as e:
        logger.error(f"✗ get_document_count failed: {str(e)}", exc_info=True)
        return 0
    finally:
        conn.close()


def delete_source(source: str) -> dict:
    """Delete all chunks from a specific source document.

    Removes all stored embeddings and metadata for a given source (filename).
    Useful for clearing outdated documents or reprocessing documents.

    Process:
    1. Validate source filename (non-empty)
    2. Establish database connection
    3. DELETE WHERE source = filename
    4. Return count of deleted chunks

    Args:
        source (str): Source filename to delete (e.g. 'report_2024.pdf').
                     This should match the 'source' field in stored chunks.

    Returns:
        dict with keys:
        - success (bool): True if deletion executed (even if 0 chunks deleted)
        - deleted (int): Number of chunks removed (0 if document not found)
        - error (str|None): Error message if success=False

    Logs:
        - INFO: Number of chunks deleted
        - ERROR: Deletion failure

    Example:
        >>> result = delete_source('old_document.pdf')
        >>> if result['success']:
        ...     print(f"Deleted {result['deleted']} chunks")

    Use cases:
        - Remove stale documents from vector store
        - Prepare for reingestion of updated document
        - Cleanup during document lifecycle management
    """
    if not source or not source.strip():
        logger.warning("⚠ delete_source: source filename is empty")
        return {"success": False, "error": "Source filename required", "deleted": 0}

    conn = get_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed", "deleted": 0}

    try:
        with conn:  # Atomic transaction
            with conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE source = %s", (source,))
                deleted = cur.rowcount

        logger.info(f"✓ Deleted {deleted} chunks for source: {source}")
        return {"success": True, "deleted": deleted, "error": None}

    except Exception as e:
        logger.error(f"✗ delete_source failed: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e), "deleted": 0}

    finally:
        conn.close()