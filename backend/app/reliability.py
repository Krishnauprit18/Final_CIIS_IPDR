"""Reliability and input-safety helpers for asynchronous analysis jobs."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DatasetValidationError(ValueError):
    """Raised when a parsed file cannot be a meaningful IPDR dataset."""

    reason: str

    def __str__(self) -> str:
        return self.reason


def validate_ipdr_frame(data: pd.DataFrame) -> dict[str, int]:
    """Validate the post-normalization minimum IPDR contract."""
    if data.empty:
        raise DatasetValidationError("Dataset contains no usable rows")

    required = {"Source IP", "Destination IP", "Protocol"}
    missing = sorted(required.difference(data.columns))
    if missing:
        raise DatasetValidationError(
            "Dataset is missing required normalized columns: " + ", ".join(missing)
        )

    valid_source = data["Source IP"].astype(str).ne("0.0.0.0")
    valid_destination = data["Destination IP"].astype(str).ne("0.0.0.0")
    valid_protocol = data["Protocol"].astype(str).str.strip().ne("")
    usable = valid_source & valid_destination & valid_protocol

    stats = {
        "rows": int(len(data)),
        "usable_rows": int(usable.sum()),
        "invalid_rows": int((~usable).sum()),
    }
    if stats["usable_rows"] == 0:
        raise DatasetValidationError(
            "Dataset contains no rows with valid source IP, destination IP, and protocol"
        )
    return stats
