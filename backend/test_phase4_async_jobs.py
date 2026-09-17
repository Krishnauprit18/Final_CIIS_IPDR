import asyncio
import json
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app.api.routers import jobs as jobs_router
from app.jobs import service as job_service
from app.workers import analysis_worker


def test_job_creation_and_lookup(monkeypatch):
    stored = {}

    def fake_create_job_record(*, case_id, job_type, payload):
        stored.update(
            {
                "id": 42,
                "case_id": case_id,
                "job_type": job_type,
                "status": "QUEUED",
                "payload_json": json.dumps(payload),
                "error_message": None,
                "progress": 0,
                "attempt_count": 0,
                "result_uri": None,
            }
        )
        return dict(stored)

    monkeypatch.setattr(job_service, "create_job_record", fake_create_job_record)
    monkeypatch.setattr(job_service, "get_job_record", lambda job_id: dict(stored) if job_id == 42 else None)

    job = job_service.create_analysis_job(
        case_id=1,
        dataset_key="inputs/test.csv",
        case_file_key=None,
    )
    assert job["status"] == "QUEUED"
    assert job_service.get_job(42)["payload"]["dataset_key"] == "inputs/test.csv"


def test_api_enqueue_success_returns_accepted_payload(monkeypatch):
    uploads = []
    messages = []

    monkeypatch.setattr(jobs_router, "get_case_record", lambda case_id: {"id": case_id})
    monkeypatch.setattr(
        jobs_router,
        "upload_fileobj",
        lambda fileobj, object_key, content_type=None: uploads.append(object_key),
    )
    monkeypatch.setattr(
        jobs_router,
        "create_analysis_job",
        lambda **kwargs: {"id": 77, "status": "QUEUED"},
    )
    monkeypatch.setattr(
        jobs_router,
        "send_analysis_message",
        lambda payload: messages.append(payload) or "message-1",
    )

    dataset = UploadFile(filename="sample.csv", file=BytesIO(b"a,b\n1,2\n"))
    response = asyncio.run(
        jobs_router.create_case_analysis(
            case_id=1,
            dataset_file=dataset,
            case_file=None,
        )
    )

    assert response == {"job_id": 77, "status": "queued"}
    assert uploads[0].startswith("analysis-inputs/1/")
    assert messages[0]["job_id"] == 77


def test_api_enqueue_failure_marks_job_failed_and_cleans_input(monkeypatch):
    failed = []
    deleted = []

    monkeypatch.setattr(jobs_router, "get_case_record", lambda case_id: {"id": case_id})
    monkeypatch.setattr(jobs_router, "upload_fileobj", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        jobs_router,
        "create_analysis_job",
        lambda **kwargs: {"id": 88, "status": "QUEUED"},
    )
    monkeypatch.setattr(
        jobs_router,
        "send_analysis_message",
        lambda payload: (_ for _ in ()).throw(RuntimeError("queue unavailable")),
    )
    monkeypatch.setattr(
        jobs_router,
        "mark_job_failed",
        lambda job_id, error: failed.append((job_id, error)),
    )
    monkeypatch.setattr(jobs_router, "delete_object", lambda key: deleted.append(key))

    dataset = UploadFile(filename="sample.csv", file=BytesIO(b"a,b\n1,2\n"))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            jobs_router.create_case_analysis(
                case_id=1,
                dataset_file=dataset,
                case_file=None,
            )
        )

    assert exc_info.value.status_code == 503
    assert failed[0][0] == 88
    assert deleted and deleted[0].startswith("analysis-inputs/1/")


def test_worker_success_completes_before_ack(monkeypatch):
    events = []

    monkeypatch.setattr(
        analysis_worker,
        "claim_analysis_job",
        lambda job_id, worker_id, lease_seconds: {"id": job_id, "status": "RUNNING"},
    )
    monkeypatch.setattr(analysis_worker, "set_job_progress", lambda *args: True)
    monkeypatch.setattr(analysis_worker, "download_bytes", lambda key: b"dataset")
    monkeypatch.setattr(analysis_worker, "_load_dataset", lambda data, filename: object())
    monkeypatch.setattr(analysis_worker, "_run_analysis", lambda df: {"rows": 1, "alerts": []})
    monkeypatch.setattr(analysis_worker, "upload_bytes", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        analysis_worker,
        "complete_job",
        lambda job_id, worker_id, result_uri: events.append("COMMIT") or True,
    )
    monkeypatch.setattr(
        analysis_worker,
        "delete_analysis_message",
        lambda receipt: events.append("ACK"),
    )

    message = {
        "Body": json.dumps({"job_id": 9, "case_id": 1, "dataset_key": "analysis-inputs/1/input.csv"}),
        "ReceiptHandle": "receipt-1",
        "Attributes": {"ApproximateReceiveCount": "1"},
    }

    analysis_worker.process_message(message, worker_id="worker-a")
    assert events == ["COMMIT", "ACK"]
