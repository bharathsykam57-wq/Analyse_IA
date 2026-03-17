"""add RAG documents table with pgvector

Revision ID: 8a4c9f7e3b2d
Revises: 6ccf48ec2b29
Create Date: 2026-03-17 10:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '8a4c9f7e3b2d'
down_revision: Union[str, Sequence[str], None] = '6ccf48ec2b29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension if not already enabled
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('source', sa.String(255), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', postgresql.UUID(), nullable=True),  # Will be vector(768) via raw SQL
        sa.Column('chunk_index', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Replace embedding column with vector type using raw SQL
    op.execute('ALTER TABLE documents DROP COLUMN IF EXISTS embedding')
    op.execute('ALTER TABLE documents ADD COLUMN embedding vector(768)')
    
    # Create indexes
    op.create_index('idx_documents_source', 'documents', ['source'])
    op.create_index('idx_documents_embedding', 'documents', ['embedding'], postgresql_using='ivfflat', postgresql_ops={'embedding': 'vector_cosine_ops'})


def downgrade() -> None:
    op.drop_index('idx_documents_embedding', table_name='documents')
    op.drop_index('idx_documents_source', table_name='documents')
    op.drop_table('documents')
    op.execute('DROP EXTENSION IF EXISTS vector')
