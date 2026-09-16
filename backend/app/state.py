from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from app.services.data_normalizer import DataNormalizer


class RuntimeState:
    """Mutable in-process analytics state retained from the original application.

    Phase 1 centralizes it behind one object; later phases will replace process-local
    state with durable/worker-oriented infrastructure.
    """

    def __init__(self) -> None:
        self.processed_data_store = pd.DataFrame()
        self.relationship_extractor = None
        self.communication_filters = None
        self.communication_mapper = None
        self.suspicious_activity_detector = None
        self.search_query_system = None
        self.data_normalizer = DataNormalizer()
        self.allowlist_ips: set[str] = set()
        self.denylist_ips: set[str] = set()
        self.case_analyses: Dict[int, Dict[str, Any]] = {}


runtime = RuntimeState()
