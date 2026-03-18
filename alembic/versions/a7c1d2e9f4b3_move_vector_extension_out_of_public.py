"""move vector extension from public to extensions schema

Revision ID: a7c1d2e9f4b3
Revises: 9f2a1e4c7b8d
Create Date: 2026-03-18 16:25:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'a7c1d2e9f4b3'
down_revision: Union[str, Sequence[str], None] = '9f2a1e4c7b8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Supabase security advisor recommends avoiding extension objects in public schema.
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_extension
                WHERE extname = 'vector'
            ) THEN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_extension e
                    JOIN pg_namespace n ON n.oid = e.extnamespace
                    WHERE e.extname = 'vector' AND n.nspname = 'extensions'
                ) THEN
                    EXECUTE 'ALTER EXTENSION vector SET SCHEMA extensions';
                END IF;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Revert extension namespace back to public (if needed).
    op.execute("CREATE SCHEMA IF NOT EXISTS public")

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_extension
                WHERE extname = 'vector'
            ) THEN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_extension e
                    JOIN pg_namespace n ON n.oid = e.extnamespace
                    WHERE e.extname = 'vector' AND n.nspname = 'public'
                ) THEN
                    EXECUTE 'ALTER EXTENSION vector SET SCHEMA public';
                END IF;
            END IF;
        END $$;
        """
    )
