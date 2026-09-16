import asyncio
import json
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app.api.routers import jobs as jobs_router
from app.jobs import service as job_service
from app.workers import analysis_worker


def test_job_lifecycle(monkeypatch):
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
            }
        )
        return dict(stored)

    def fake_get_job_record(job_id):
        return dict(stored) if job_id == 42 else None

    def fake_update_job_status(job_id, status, *, error_message=None):
        assert job_id == 42
        stored["status"] = status
        stored["error_message"] = error_message

    monkeypatch.setattr(job_service, "create_job_record", fake_create_job_record)
    monkeypatch.setattr(job_service, "get_job_record", fake_get_job_record)
    monkeypatch.setattr(job_service, "update_job_status", fake_update_job_status)

    job = job_service.create_analysis_job(
        case_id=1,
        dataset_key="inputs/test.csv",
        case_file_key=None,
    )
    assert job["status"] == "QUEUED"

    job_service.mark_job_running(42)
    assert job_service.get_job(42)["status"] == "RUNNING"

    job_service.mark_job_retrying(42, "temporary failure")
    assert job_service.get_job(42)["status"] == "QUEUED"

    job_service.mark_job_succeeded(42)
    assert job_service.get_job(42)["status"] == "SUCCEEDED"
    assert job_service.job_is_terminal(42) is True


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
    assert len(uploads) == 1
    assert uploads[0].startswith("analysis-inputs/1/")
    assert messages[0]["job_id"] == 77
    assert messages[0]["case_id"] == 1


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

    def fail_send(payload):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(jobs_router, "send_analysis_message", fail_send)
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
    assert failed and failed[0][0] == 88
    assert len(deleted) == 1
    assert deleted[0].startswith("analysis-inputs/1/")


def test_worker_success_acknowledges_message(monkeypatch):
    events = []
    uploaded = []

    monkeypatch.setattr(analysis_worker, "get_job", lambda job_id: {"id": job_id, "status": "QUEUED"})
    monkeypatch.setattr(analysis_worker, "mark_job_running", lambda job_id: events.append(("RUNNING", job_id)))
    monkeypatch.setattr(analysis_worker, "mark_job_succeeded", lambda job_id: events.append(("SUCCEEDED", job_id)))
    monkeypatch.setattr(analysis_worker, "download_bytes", lambda key: b"dataset")
    monkeypatch.setattr(analysis_worker, "_load_dataset", lambda data, filename: object())
    monkeypatch.setattr(analysis_worker, "_run_analysis", lambda df: {"rows": 1, "alerts": []})
    monkeypatch.setattr(
        analysis_worker,
        "upload_bytes",
        lambda data, key, content_type=None: uploaded.append((key, data)),
    )
    monkeypatch.setattr(
        analysis_worker,
        "delete_analysis_message",
        lambda receipt: events.append(("ACK", receipt)),
    )

    message = {
        "Body": json.dumps(
            {
                "job_id": 9,
                "case_id": 1,
                "dataset_key": "analysis-inputs/1/input.csv",
            }
        ),
        "ReceiptHandle": "receipt-1",
        "Attributes": {"ApproximateReceiveCount": "1"},
    }

    analysis_worker.process_message(message)

    assert ("RUNNING", 9) in events
    assert ("SUCCEEDED", 9) in events
    assert ("ACK", "receipt-1") in events
    assert uploaded[0][0] == "analysis-results/1/9/result.json"


def test_worker_third_failure_marks_failed_without_ack(monkeypatch):
    failed = []
    retried = []
    acknowledged = []

    monkeypatch.setattr(analysis_worker, "get_job", lambda job_id: {"id": job_id, "status": "QUEUED"})
    monkeypatch.setattr(analysis_worker, "mark_job_running", lambda job_id: None)
    monkeypatch.setattr(
        analysis_worker,
        "download_bytes",
        lambda key: (_ for _ in ()).throw(RuntimeError("missing object")),
    )
    monkeypatch.setattr(
        analysis_worker,
        "mark_job_failed",
        lambda job_id, error: failed.append((job_id, error)),
    )
    monkeypatch.setattr(
        analysis_worker,
        "mark_job_retrying",
        lambda job_id, error: retried.append((job_id, error)),
    )
    monkeypatch.setattr(
        analysis_worker,
        "delete_analysis_message",
        lambda receipt: acknowledged.append(receipt),
    )

    message = {
        "Body": json.dumps(
            {
                "job_id": 10,
                "case_id": 1,
                "dataset_key": "analysis-inputs/missing.csv",
            }
        ),
        "ReceiptHandle": "receipt-2",
        "Attributes": {"ApproximateReceiveCount": "3"},
    }

    with pytest.raises(RuntimeError, match="missing object"):
        analysis_worker.process_message(message)

    assert failed and failed[0][0] == 10
    assert retried == []
    assert acknowledged == []
