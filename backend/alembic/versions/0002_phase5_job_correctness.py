"""Phase 5 job correctness fields.

Revision ID: 0002_phase5_job_correctness
Revises: 0001_initial_postgresql
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_phase5_job_correctness"
down_revision = "0001_initial_postgresql"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("progress", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("jobs", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("jobs", sa.Column("worker_id", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("claim_expires_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("jobs", sa.Column("started_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("jobs", sa.Column("finished_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("jobs", sa.Column("result_uri", sa.Text(), nullable=True))
    op.create_index("ix_jobs_worker_id", "jobs", ["worker_id"], unique=False)
    op.create_index("ix_jobs_claim_expires_at", "jobs", ["claim_expires_at"], unique=False)
    op.alter_column("jobs", "progress", server_default=None)
    op.alter_column("jobs", "attempt_count", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_jobs_claim_expires_at", table_name="jobs")
    op.drop_index("ix_jobs_worker_id", table_name="jobs")
    op.drop_column("jobs", "result_uri")
    op.drop_column("jobs", "finished_at")
    op.drop_column("jobs", "started_at")
    op.drop_column("jobs", "claim_expires_at")
    op.drop_column("jobs", "worker_id")
    op.drop_column("jobs", "attempt_count")
    op.drop_column("jobs", "progress")
