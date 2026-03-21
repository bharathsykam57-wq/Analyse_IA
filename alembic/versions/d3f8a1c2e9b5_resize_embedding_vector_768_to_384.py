"""resize embedding column from vector(768) to vector(384)

Switches the RAG embedding model from paraphrase-multilingual-mpnet-base-v2 (768-dim,
~1 GB download) to all-MiniLM-L6-v2 (384-dim, ~90 MB download).

Existing 768-dim vectors are incompatible with the new model — all stored chunks are
deleted as part of this migration. Documents must be re-indexed after deployment.

Revision ID: d3f8a1c2e9b5
Revises: 8a4c9f7e3b2d
Create Date: 2026-03-21 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "d3f8a1c2e9b5"
down_revision: Union[str, Sequence[str], None] = "8a4c9f7e3b2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the ivfflat index — it is tied to the column type and dimension
    op.execute("DROP INDEX IF EXISTS idx_documents_embedding")

    # Remove all stored chunks: 768-dim vectors are incompatible with the new 384-dim model.
    # Documents will be re-indexed automatically on next upload / warm task.
    op.execute("TRUNCATE TABLE documents")

    # Replace the embedding column with the correct 384-dim type
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE documents ADD COLUMN embedding vector(384)")

    # Recreate the cosine-distance ivfflat index for the new dimension
    op.execute(
        "CREATE INDEX idx_documents_embedding ON documents "
        "USING ivfflat (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_documents_embedding")
    op.execute("TRUNCATE TABLE documents")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE documents ADD COLUMN embedding vector(768)")
    op.execute(
        "CREATE INDEX idx_documents_embedding ON documents "
        "USING ivfflat (embedding vector_cosine_ops)"
    )
