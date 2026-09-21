from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text

from app.reliability import DatasetValidationError, validate_ipdr_frame
from app.storage.service import sha256_bytes
from app.workers import analysis_worker


def _message() -> dict:
    return {
        "Body": '{"job_id": 91, "case_id": 4, "dataset_key": "analysis-inputs/4/bad.csv"}',
        "ReceiptHandle": "receipt-91",
        "Attributes": {"ApproximateReceiveCount": "1"},
    }


def _frame(source: str = "10.0.0.1") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Source IP": [source],
            "Destination IP": ["8.8.8.8"],
            "Protocol": ["TCP"],
        }
    )


def test_valid_ipdr_frame_returns_validation_counts() -> None:
    assert validate_ipdr_frame(_frame()) == {
        "rows": 1,
        "usable_rows": 1,
        "invalid_rows": 0,
    }


def test_invalid_ipdr_frame_is_rejected_as_permanent_input() -> None:
    with pytest.raises(DatasetValidationError, match="no rows"):
        validate_ipdr_frame(_frame(source="0.0.0.0"))


def test_object_hash_is_stable_and_sha256_length_is_explicit() -> None:
    first = sha256_bytes(b"ciis-phase-22")
    second = sha256_bytes(b"ciis-phase-22")

    assert first == second
    assert len(first) == 64
    assert first != sha256_bytes(b"different")


def test_worker_quarantines_invalid_input_and_acknowledges_message(monkeypatch) -> None:
    failed = []
    quarantined = []
    acked = []

    monkeypatch.setattr(
        analysis_worker,
        "claim_analysis_job",
        lambda *args, **kwargs: {"id": 91, "status": "RUNNING", "payload_json": "{}"},
    )
    monkeypatch.setattr(analysis_worker, "set_job_progress", lambda *args: True)
    monkeypatch.setattr(analysis_worker, "download_bytes", lambda key: b"invalid")
    monkeypatch.setattr(
        analysis_worker,
        "_load_dataset",
        lambda data, filename: _frame(source="0.0.0.0"),
    )
    monkeypatch.setattr(
        analysis_worker,
        "quarantine_bytes",
        lambda *args, **kwargs: quarantined.append(kwargs) or ("quarantine/4/91/x-bad.csv", "a" * 64),
    )
    monkeypatch.setattr(analysis_worker, "fail_job", lambda *args: failed.append(args) or True)
    monkeypatch.setattr(analysis_worker, "delete_analysis_message", lambda value: acked.append(value))
    monkeypatch.setattr(analysis_worker, "update_job_payload", lambda *args: None)
    monkeypatch.setattr(analysis_worker, "update_job_integrity", lambda *args, **kwargs: None)

    analysis_worker.process_message(_message(), worker_id="worker-invalid")

    assert failed and "Invalid IPDR input" in failed[0][2]
    assert quarantined
    assert acked == ["receipt-91"]


def test_worker_fails_missing_object_without_retry_loop(monkeypatch) -> None:
    failed = []
    acked = []

    monkeypatch.setattr(
        analysis_worker,
        "claim_analysis_job",
        lambda *args, **kwargs: {"id": 91, "status": "RUNNING", "payload_json": "{}"},
    )
    monkeypatch.setattr(analysis_worker, "set_job_progress", lambda *args: True)
    monkeypatch.setattr(
        analysis_worker,
        "download_bytes",
        lambda key: (_ for _ in ()).throw(analysis_worker.ObjectMissingError("missing")),
    )
    monkeypatch.setattr(analysis_worker, "fail_job", lambda *args: failed.append(args) or True)
    monkeypatch.setattr(analysis_worker, "delete_analysis_message", lambda value: acked.append(value))
    monkeypatch.setattr(analysis_worker, "update_job_payload", lambda *args: None)
    monkeypatch.setattr(analysis_worker, "update_job_integrity", lambda *args, **kwargs: None)

    analysis_worker.process_message(_message(), worker_id="worker-missing")

    assert failed and failed[0][0] == 91
    assert acked == ["receipt-91"]


def test_phase_22_migration_protects_audit_events_and_adds_integrity_fields() -> None:
    migration = (
        Path(__file__).parent
        / "alembic"
        / "versions"
        / "0005_phase21_22_reliability_data_protection.py"
    ).read_text(encoding="utf-8")

    assert "audit_events_append_only" in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert 'sa.Column("input_sha256"' in migration
    assert 'sa.Column("result_sha256"' in migration
    assert 'sa.Column("quarantine_uri"' in migration


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="requires disposable PostgreSQL")
def test_audit_events_reject_update_and_delete() -> None:
    from app.db.session import get_engine

    with get_engine().begin() as connection:
        event_id = connection.execute(
            text(
                """
                INSERT INTO audit_events (action, outcome, created_at)
                VALUES ('phase22_test', 'success', :created_at)
                RETURNING id
                """
            ),
            {"created_at": datetime.now()},
        ).scalar_one()

    with pytest.raises(Exception, match="append-only"):
        with get_engine().begin() as connection:
            connection.execute(
                text("UPDATE audit_events SET outcome = 'failed' WHERE id = :id"),
                {"id": event_id},
            )

    with pytest.raises(Exception, match="append-only"):
        with get_engine().begin() as connection:
            connection.execute(
                text("DELETE FROM audit_events WHERE id = :id"),
                {"id": event_id},
            )
