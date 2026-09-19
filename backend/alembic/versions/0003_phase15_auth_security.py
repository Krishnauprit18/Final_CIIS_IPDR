"""Phase 15 authentication hardening and per-case authorization."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_phase15_auth_security"
down_revision = "0002_phase5_job_correctness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=50),
            nullable=False,
            server_default="analyst",
        ),
    )
    op.alter_column("users", "role", server_default=None)

    op.create_table(
        "case_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "case_id", name="uq_case_memberships_user_case"),
    )
    op.create_index("ix_case_memberships_user_id", "case_memberships", ["user_id"])
    op.create_index("ix_case_memberships_case_id", "case_memberships", ["case_id"])
    op.alter_column("case_memberships", "role", server_default=None)

    # Tokens created before Phase 15 were persisted in plaintext. Invalidate
    # them before the application starts storing only token digests.
    op.execute("DELETE FROM sessions")


def downgrade() -> None:
    op.drop_index("ix_case_memberships_case_id", table_name="case_memberships")
    op.drop_index("ix_case_memberships_user_id", table_name="case_memberships")
    op.drop_table("case_memberships")
    op.drop_column("users", "role")
