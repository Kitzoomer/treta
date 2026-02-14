from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


LaunchMetrics = Dict[str, Any]


class LaunchMetricsModule:
    """Utility helpers for launch metrics payloads."""

    @staticmethod
    def default() -> LaunchMetrics:
        return {
            "views": 0,
            "clicks": 0,
            "sales": 0,
            "revenue": 0.0,
        }

    @staticmethod
    def normalize(metrics: Dict[str, Any] | None) -> LaunchMetrics:
        payload = dict(metrics or {})
        return {
            "views": int(payload.get("views", 0) or 0),
            "clicks": int(payload.get("clicks", 0) or 0),
            "sales": int(payload.get("sales", 0) or 0),
            "revenue": float(payload.get("revenue", 0.0) or 0.0),
        }

    @staticmethod
    def add_sale(metrics: Dict[str, Any], amount: float) -> LaunchMetrics:
        updated = LaunchMetricsModule.normalize(metrics)
        updated["sales"] += 1
        updated["revenue"] = round(updated["revenue"] + float(amount), 2)
        return deepcopy(updated)
