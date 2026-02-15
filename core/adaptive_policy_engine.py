from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List


class AdaptivePolicyEngine:
    """Deterministic adaptive tuning for autonomy thresholds."""

    _DEFAULT_DATA_DIR = "./.treta_data"

    def __init__(
        self,
        path: Path | None = None,
        impact_threshold: int = 6,
        max_auto_executions_per_24h: int = 3,
    ):
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "adaptive_policy_state.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)

        self._state: Dict[str, Any] = {
            "total_auto_executed_actions": 0,
            "successful_actions": 0,
            "revenue_delta_per_action": [],
            "impact_threshold": self._clamp(int(impact_threshold), 4, 8),
            "max_auto_executions_per_24h": self._clamp(int(max_auto_executions_per_24h), 1, 5),
        }
        loaded = self._load_state()
        if loaded is not None:
            self._state = loaded

    def _clamp(self, value: int, minimum: int, maximum: int) -> int:
        return min(max(value, minimum), maximum)

    def _load_state(self) -> Dict[str, Any] | None:
        if not self._path.exists():
            return None

        loaded = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return None

        deltas = loaded.get("revenue_delta_per_action", [])
        normalized_deltas: List[float] = []
        if isinstance(deltas, list):
            for item in deltas:
                try:
                    normalized_deltas.append(float(item))
                except (TypeError, ValueError):
                    continue

        total = int(loaded.get("total_auto_executed_actions", len(normalized_deltas)) or 0)
        successful = int(loaded.get("successful_actions", 0) or 0)

        return {
            "total_auto_executed_actions": max(total, 0),
            "successful_actions": self._clamp(successful, 0, max(total, 0)),
            "revenue_delta_per_action": normalized_deltas,
            "impact_threshold": self._clamp(int(loaded.get("impact_threshold", 6) or 6), 4, 8),
            "max_auto_executions_per_24h": self._clamp(
                int(loaded.get("max_auto_executions_per_24h", 3) or 3),
                1,
                5,
            ),
        }

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def _success_rate(self) -> float:
        total = int(self._state["total_auto_executed_actions"])
        if total <= 0:
            return 0.0
        return float(self._state["successful_actions"]) / float(total)

    def _average_revenue_delta(self) -> float:
        deltas = self._state["revenue_delta_per_action"]
        if not deltas:
            return 0.0
        return float(sum(deltas)) / float(len(deltas))

    def _recompute_adaptive_parameters(self) -> None:
        success_rate = self._success_rate()
        avg_revenue_delta = self._average_revenue_delta()

        impact_threshold = int(self._state["impact_threshold"])
        if success_rate > 0.7:
            impact_threshold -= 1
        elif success_rate < 0.4:
            impact_threshold += 1
        self._state["impact_threshold"] = self._clamp(impact_threshold, 4, 8)

        max_auto_exec = int(self._state["max_auto_executions_per_24h"])
        if avg_revenue_delta > 100:
            max_auto_exec += 1
        elif avg_revenue_delta < 0:
            max_auto_exec -= 1
        self._state["max_auto_executions_per_24h"] = self._clamp(max_auto_exec, 1, 5)

    def record_action_outcome(self, revenue_delta: float) -> Dict[str, Any]:
        delta = float(revenue_delta)
        self._state["total_auto_executed_actions"] += 1
        if delta > 0:
            self._state["successful_actions"] += 1
        self._state["revenue_delta_per_action"].append(delta)
        self._recompute_adaptive_parameters()
        self._save()
        return self.adaptive_status()

    def adaptive_status(self) -> Dict[str, Any]:
        return {
            "success_rate": self._success_rate(),
            "avg_revenue_delta": self._average_revenue_delta(),
            "impact_threshold": int(self._state["impact_threshold"]),
            "max_auto_executions_per_24h": int(self._state["max_auto_executions_per_24h"]),
        }

    def tracked_metrics(self) -> Dict[str, Any]:
        return deepcopy(
            {
                "total_auto_executed_actions": int(self._state["total_auto_executed_actions"]),
                "successful_actions": int(self._state["successful_actions"]),
                "revenue_delta_per_action": list(self._state["revenue_delta_per_action"]),
            }
        )
