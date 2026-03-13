"""add experiment_runs table

Revision ID: 6ccf48ec2b29
Revises: 780837f28fa1
Create Date: 2026-03-13 22:01:29.482183
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '6ccf48ec2b29'
down_revision: Union[str, Sequence[str], None] = '780837f28fa1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'experiment_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('task_type', sa.String(), nullable=False),
        sa.Column('question', sa.String(), nullable=False),
        sa.Column('answer_preview', sa.String(), nullable=True),
        sa.Column('dataset_rows', sa.Integer(), nullable=True),
        sa.Column('dataset_columns', sa.Integer(), nullable=True),
        sa.Column('best_model', sa.String(), nullable=True),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('auc', sa.Float(), nullable=True),
        sa.Column('f1', sa.Float(), nullable=True),
        sa.Column('anomaly_count', sa.Integer(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('language', sa.String(), nullable=True),
        sa.Column('extra', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_experiment_runs_user_id', 'experiment_runs', ['user_id'])
    op.create_index('ix_experiment_runs_created_at', 'experiment_runs', ['created_at'])
    op.create_index('ix_experiment_runs_task_type', 'experiment_runs', ['task_type'])


def downgrade() -> None:
    op.drop_index('ix_experiment_runs_task_type', table_name='experiment_runs')
    op.drop_index('ix_experiment_runs_created_at', table_name='experiment_runs')
    op.drop_index('ix_experiment_runs_user_id', table_name='experiment_runs')
    op.drop_table('experiment_runs')
