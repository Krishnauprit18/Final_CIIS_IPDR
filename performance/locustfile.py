from __future__ import annotations

import os
from pathlib import Path

from locust import HttpUser, between, task
from locust.exception import StopUser


USERNAME = os.getenv("CIIS_USERNAME", "")
PASSWORD = os.getenv("CIIS_PASSWORD", "")
DATASET_PATH = Path(os.getenv("CIIS_DATASET_PATH", ""))
CASE_ID = os.getenv("CIIS_CASE_ID", "")


class AuthenticatedUser(HttpUser):
    """Read/login workload; no default credentials are embedded in the repo."""

    wait_time = between(1, 3)

    def on_start(self) -> None:
        if not USERNAME or not PASSWORD:
            raise StopUser("Set CIIS_USERNAME and CIIS_PASSWORD for the load test")
        response = self.client.post(
            "/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
            name="POST /auth/login",
        )
        response.raise_for_status()
        token = response.json().get("token")
        if not token:
            raise StopUser("Login response did not contain an access token")
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(5)
    def read_cases(self) -> None:
        self.client.get("/cases", name="GET /cases")

    @task(2)
    def read_profile(self) -> None:
        self.client.get("/auth/me", name="GET /auth/me")

    @task(1)
    def liveness(self) -> None:
        self.client.get("/health/live", name="GET /health/live")


class AnalysisUser(AuthenticatedUser):
    """Submission plus status-polling workload for a real fixture or dataset."""

    wait_time = between(2, 5)

    def on_start(self) -> None:
        super().on_start()
        if not DATASET_PATH.is_file():
            raise StopUser("Set CIIS_DATASET_PATH to a real IPDR fixture")
        self.case_id = int(CASE_ID) if CASE_ID.isdigit() else self._create_case()

    def _create_case(self) -> int:
        response = self.client.post(
            "/cases",
            json={"name": "phase-23-load-test"},
            name="POST /cases",
        )
        response.raise_for_status()
        return int(response.json()["id"])

    @task
    def submit_and_poll(self) -> None:
        with DATASET_PATH.open("rb") as dataset:
            response = self.client.post(
                f"/cases/{self.case_id}/analysis",
                files={
                    "dataset_file": (
                        DATASET_PATH.name,
                        dataset,
                        "text/csv",
                    )
                },
                name="POST /cases/{case_id}/analysis",
            )
        if response.status_code >= 400:
            return

        job_id = response.json().get("job_id")
        if not job_id:
            return
        for _ in range(int(os.getenv("CIIS_MAX_POLL_COUNT", "120"))):
            status = self.client.get(
                f"/jobs/{job_id}",
                name="GET /jobs/{job_id}",
            )
            if status.status_code >= 400 or status.json().get("status") in {"SUCCEEDED", "FAILED"}:
                break
            self.wait()
