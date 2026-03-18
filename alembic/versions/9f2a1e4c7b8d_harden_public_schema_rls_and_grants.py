"""harden public schema grants and enable rls on exposed tables

Revision ID: 9f2a1e4c7b8d
Revises: 8a4c9f7e3b2d
Create Date: 2026-03-18 16:05:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = '9f2a1e4c7b8d'
down_revision: Union[str, Sequence[str], None] = '8a4c9f7e3b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EXPOSED_TABLES = [
    'alembic_version',
    'users',
    'refresh_tokens',
    'consents',
    'audit_logs',
    'experiment_runs',
    'documents',
]


def upgrade() -> None:
    # Restrict direct API-role access on public schema objects.
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated")
    op.execute("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated")

    # Ensure future objects in public are not auto-granted to API roles.
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon, authenticated")

    # Enable RLS on exposed tables to satisfy security advisor checks.
    # NOTE: We intentionally do NOT use FORCE ROW LEVEL SECURITY here to avoid
    # breaking direct backend DB access patterns.
    for table_name in EXPOSED_TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table_name}') IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY';
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    # Re-enable grants to API roles (reversal of this migration).
    op.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated")
    op.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated")
    op.execute("GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated")

    # Disable RLS on tables touched by this migration.
    for table_name in EXPOSED_TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table_name}') IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE public.{table_name} DISABLE ROW LEVEL SECURITY';
                END IF;
            END $$;
            """
        )
