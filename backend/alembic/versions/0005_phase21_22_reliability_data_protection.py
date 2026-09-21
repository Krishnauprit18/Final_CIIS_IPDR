"""Reliability metadata and append-only audit-event protection."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_reliability_protection"
down_revision = "0004_phase15_auth_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Audit events are intentionally insert-only.  This is a database guard,
    # not merely an application convention, so every application path gets the
    # same protection.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events are append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_event_mutation();
        """
    )

    op.add_column(
        "jobs",
        sa.Column("input_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("result_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("quarantine_uri", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "quarantine_uri")
    op.drop_column("jobs", "result_sha256")
    op.drop_column("jobs", "input_sha256")
    op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_event_mutation()")
