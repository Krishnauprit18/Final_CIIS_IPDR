import json

import pytest

from app.workers import analysis_worker


def _message(job_id=5, receive_count="1"):
    return {
        "Body": json.dumps(
            {
                "job_id": job_id,
                "case_id": 1,
                "dataset_key": "analysis-inputs/1/input.csv",
            }
        ),
        "ReceiptHandle": f"receipt-{job_id}",
        "Attributes": {"ApproximateReceiveCount": receive_count},
    }


def test_duplicate_succeeded_message_is_acknowledged_without_processing(monkeypatch):
    acked = []
    processed = []

    monkeypatch.setattr(
        analysis_worker,
        "claim_analysis_job",
        lambda job_id, worker_id, lease_seconds: {"id": job_id, "status": "SUCCEEDED"},
    )
    monkeypatch.setattr(analysis_worker, "download_bytes", lambda key: processed.append(key))
    monkeypatch.setattr(analysis_worker, "delete_analysis_message", lambda receipt: acked.append(receipt))

    analysis_worker.process_message(_message(), worker_id="worker-b")

    assert acked == ["receipt-5"]
    assert processed == []


def test_live_claim_owned_by_other_worker_is_not_acknowledged(monkeypatch):
    acked = []
    monkeypatch.setattr(analysis_worker, "claim_analysis_job", lambda *args, **kwargs: None)
    monkeypatch.setattr(analysis_worker, "delete_analysis_message", lambda receipt: acked.append(receipt))

    analysis_worker.process_message(_message(), worker_id="worker-b")

    assert acked == []


def test_partial_failure_requeues_without_ack(monkeypatch):
    retried = []
    acked = []

    monkeypatch.setattr(
        analysis_worker,
        "claim_analysis_job",
        lambda job_id, worker_id, lease_seconds: {"id": job_id, "status": "RUNNING"},
    )
    monkeypatch.setattr(analysis_worker, "set_job_progress", lambda *args: True)
    monkeypatch.setattr(
        analysis_worker,
        "download_bytes",
        lambda key: (_ for _ in ()).throw(RuntimeError("temporary storage failure")),
    )
    monkeypatch.setattr(
        analysis_worker,
        "retry_job",
        lambda job_id, worker_id, error: retried.append((job_id, worker_id, error)) or True,
    )
    monkeypatch.setattr(analysis_worker, "fail_job", lambda *args: pytest.fail("must not fail on first receive"))
    monkeypatch.setattr(analysis_worker, "delete_analysis_message", lambda receipt: acked.append(receipt))

    with pytest.raises(RuntimeError, match="temporary storage failure"):
        analysis_worker.process_message(_message(), worker_id="worker-c")

    assert retried and retried[0][0] == 5
    assert acked == []


def test_third_failure_marks_failed_without_ack(monkeypatch):
    failed = []
    acked = []

    monkeypatch.setattr(
        analysis_worker,
        "claim_analysis_job",
        lambda job_id, worker_id, lease_seconds: {"id": job_id, "status": "RUNNING"},
    )
    monkeypatch.setattr(analysis_worker, "set_job_progress", lambda *args: True)
    monkeypatch.setattr(
        analysis_worker,
        "download_bytes",
        lambda key: (_ for _ in ()).throw(RuntimeError("bad input")),
    )
    monkeypatch.setattr(analysis_worker, "retry_job", lambda *args: pytest.fail("third receive must fail terminally"))
    monkeypatch.setattr(
        analysis_worker,
        "fail_job",
        lambda job_id, worker_id, error: failed.append((job_id, worker_id, error)) or True,
    )
    monkeypatch.setattr(analysis_worker, "delete_analysis_message", lambda receipt: acked.append(receipt))

    with pytest.raises(RuntimeError, match="bad input"):
        analysis_worker.process_message(_message(receive_count="3"), worker_id="worker-d")

    assert failed and failed[0][0] == 5
    assert acked == []


def test_crash_after_db_commit_does_not_repeat_analysis(monkeypatch):
    uploads = []
    claims = iter(
        [
            {"id": 5, "status": "RUNNING"},
            {"id": 5, "status": "SUCCEEDED"},
        ]
    )
    delete_calls = []

    monkeypatch.setattr(analysis_worker, "claim_analysis_job", lambda *args, **kwargs: next(claims))
    monkeypatch.setattr(analysis_worker, "set_job_progress", lambda *args: True)
    monkeypatch.setattr(analysis_worker, "download_bytes", lambda key: b"dataset")
    monkeypatch.setattr(analysis_worker, "_load_dataset", lambda data, filename: object())
    monkeypatch.setattr(analysis_worker, "_run_analysis", lambda df: {"rows": 1})
    monkeypatch.setattr(
        analysis_worker,
        "upload_bytes",
        lambda data, key, content_type=None: uploads.append(key),
    )
    monkeypatch.setattr(analysis_worker, "complete_job", lambda *args: True)
    monkeypatch.setattr(analysis_worker, "retry_job", lambda *args: False)
    monkeypatch.setattr(analysis_worker, "fail_job", lambda *args: False)

    def flaky_delete(receipt):
        delete_calls.append(receipt)
        if len(delete_calls) == 1:
            raise RuntimeError("worker crashed after commit")

    monkeypatch.setattr(analysis_worker, "delete_analysis_message", flaky_delete)

    with pytest.raises(RuntimeError, match="worker crashed after commit"):
        analysis_worker.process_message(_message(), worker_id="worker-e")

    analysis_worker.process_message(_message(), worker_id="worker-f")

    assert uploads == ["analysis-results/1/5/result.json"]
    assert delete_calls == ["receipt-5", "receipt-5"]
