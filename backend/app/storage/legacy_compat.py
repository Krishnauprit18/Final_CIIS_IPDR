from __future__ import annotations

import os
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

from app.storage.service import upload_bytes, upload_path


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")


def install_legacy_object_storage_compat(legacy_handlers: Any) -> None:
    """Redirect durable legacy artifacts from local disk to object storage.

    Temporary local files used only while parsers process an upload are still
    allowed; anything returned/persisted as an artifact is moved to S3/MinIO.
    """

    def persist_processed_data(df, base_name: str = "processed"):
        try:
            payload = df.to_csv(index=False).encode("utf-8")
            key = f"processed/{base_name}_{_timestamp()}.csv"
            return upload_bytes(payload, key, content_type="text/csv")
        except Exception:
            return None

    legacy_handlers._persist_processed_data = persist_processed_data

    original_ai_analyze_case = legacy_handlers.ai_analyze_case

    @wraps(original_ai_analyze_case)
    async def ai_analyze_case(*args, **kwargs):
        response = await original_ai_analyze_case(*args, **kwargs)
        case_id = kwargs.get("case_id")
        if case_id is None and args:
            case_id = args[0]
        analysis = legacy_handlers.CASE_ANALYSES.get(case_id)
        if analysis:
            local_path = analysis.get("case_doc_path")
            if local_path and os.path.exists(local_path):
                filename = Path(local_path).name
                uri = upload_path(
                    local_path,
                    f"cases/{case_id}/documents/{filename}",
                    delete_local=True,
                )
                analysis["case_doc_path"] = uri
                if isinstance(response, dict):
                    response["case_document"] = uri
        return response

    legacy_handlers.ai_analyze_case = ai_analyze_case

    original_export_case_pack = legacy_handlers.export_case_pack

    @wraps(original_export_case_pack)
    def export_case_pack(*args, **kwargs):
        response = original_export_case_pack(*args, **kwargs)
        if isinstance(response, dict):
            local_path = response.get("export_file")
            if local_path and os.path.exists(local_path):
                filename = Path(local_path).name
                response["export_file"] = upload_path(
                    local_path,
                    f"exports/cases/{filename}",
                    content_type="application/zip",
                    delete_local=True,
                )
        return response

    legacy_handlers.export_case_pack = export_case_pack

    original_export_alerts = legacy_handlers.export_suspicious_alerts

    @wraps(original_export_alerts)
    async def export_suspicious_alerts(*args, **kwargs):
        response = await original_export_alerts(*args, **kwargs)
        if isinstance(response, dict):
            local_path = response.get("export_file")
            if local_path and os.path.exists(local_path):
                filename = Path(local_path).name
                response["export_file"] = upload_path(
                    local_path,
                    f"exports/alerts/{filename}",
                    content_type="text/csv",
                    delete_local=True,
                )
        return response

    legacy_handlers.export_suspicious_alerts = export_suspicious_alerts

    original_export_search = legacy_handlers.export_search_results

    @wraps(original_export_search)
    def export_search_results(*args, **kwargs):
        response = original_export_search(*args, **kwargs)
        if isinstance(response, dict):
            local_path = response.get("filename") or response.get("export_file")
            if local_path and os.path.exists(local_path):
                filename = Path(local_path).name
                uri = upload_path(
                    local_path,
                    f"exports/search/{filename}",
                    content_type="text/csv",
                    delete_local=True,
                )
                if "filename" in response:
                    response["filename"] = uri
                else:
                    response["export_file"] = uri
        return response

    legacy_handlers.export_search_results = export_search_results
