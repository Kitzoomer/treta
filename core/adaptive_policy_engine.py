from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from core.storage import Storage


class AdaptivePolicyEngine:
    """Deterministic adaptive tuning for autonomy thresholds."""

    _DEFAULT_DATA_DIR = "./.treta_data"
    _DEFAULT_STRATEGY_WEIGHTS = {
        "scale": 1.0,
        "review": 1.0,
        "price_test": 1.0,
        "new_product": 1.0,
        "archive": 1.0,
    }
    MIN_STRATEGY_WEIGHT = 0.1
    MAX_STRATEGY_WEIGHT = 3.0

    def __init__(
        self,
        path: Path | None = None,
        impact_threshold: int = 6,
        max_auto_executions_per_24h: int = 3,
        storage: Storage | None = None,
    ):
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "adaptive_policy_state.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._storage = storage
        self._logger = logging.getLogger("treta.adaptive_policy")

        self._state: Dict[str, Any] = {
            "total_auto_executed_actions": 0,
            "successful_actions": 0,
            "revenue_delta_per_action": [],
            "impact_threshold": self._clamp(int(impact_threshold), 4, 8),
            "max_auto_executions_per_24h": self._clamp(int(max_auto_executions_per_24h), 1, 5),
            "strategy_weights": dict(self._DEFAULT_STRATEGY_WEIGHTS),
        }
        loaded = self._load_state()
        if loaded is not None:
            self._state = loaded

    def _clamp(self, value: int, minimum: int, maximum: int) -> int:
        return min(max(value, minimum), maximum)

    def _normalized_weights(self, raw: Any) -> Dict[str, float]:
        merged = dict(self._DEFAULT_STRATEGY_WEIGHTS)
        if not isinstance(raw, dict):
            return merged
        for strategy_type, weight in raw.items():
            try:
                merged[str(strategy_type)] = max(float(weight), 0.0)
            except (TypeError, ValueError):
                continue
        return merged

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
            "strategy_weights": self._normalized_weights(loaded.get("strategy_weights")),
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

    def _normalize_scores(self, scores: Dict[str, float]) -> Dict[str, float]:
        if not scores:
            return {}
        max_score = max(scores.values())
        if max_score <= 0:
            return {key: 0.0 for key in scores}
        return {key: value / max_score for key, value in scores.items()}

    def refresh_strategy_weights(self) -> Dict[str, float]:
        if self._storage is None:
            return dict(self._state["strategy_weights"])

        performance = self._storage.get_strategy_performance()
        if not performance:
            return dict(self._state["strategy_weights"])

        eligible = {
            strategy_type: metrics
            for strategy_type, metrics in performance.items()
            if int(metrics.get("total_decisions", 0) or 0) >= 5
        }
        if not eligible:
            return dict(self._state["strategy_weights"])

        sorted_eligible = sorted(eligible.items(), key=lambda item: float(item[1].get("score", 0) or 0), reverse=True)
        normalized_scores = self._normalize_scores({key: float(metrics.get("score", 0) or 0) for key, metrics in sorted_eligible})

        weights = dict(self._state["strategy_weights"])
        for strategy_type, metrics in sorted_eligible:
            old_weight = float(weights.get(strategy_type, 1.0) or 1.0)
            score = float(metrics.get("score", 0) or 0)
            score_normalized = float(normalized_scores.get(strategy_type, 0.0) or 0.0)
            new_weight = (old_weight * 0.7) + (score_normalized * 0.3)
            clamped_weight = max(self.MIN_STRATEGY_WEIGHT, min(new_weight, self.MAX_STRATEGY_WEIGHT))
            weights[strategy_type] = clamped_weight
            if new_weight != clamped_weight:
                self._logger.info(
                    "adaptive_strategy_weight_clamped",
                    extra={
                        "strategy_type": strategy_type,
                        "old_weight": old_weight,
                        "raw_new_weight": new_weight,
                        "clamped_weight": clamped_weight,
                        "reason": "weight_clamped",
                    },
                )
            self._logger.info(
                "adaptive_strategy_weight_updated",
                extra={
                    "strategy_type": strategy_type,
                    "old_weight": old_weight,
                    "new_weight": clamped_weight,
                    "score": score,
                },
            )

        self._state["strategy_weights"] = weights
        self._save()
        return dict(self._state["strategy_weights"])

    def prioritized_strategy_types(self, strategy_types: List[str]) -> List[str]:
        if not strategy_types:
            return []
        current_weights = self.refresh_strategy_weights()
        return sorted(strategy_types, key=lambda item: float(current_weights.get(item, 1.0) or 1.0), reverse=True)

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
            "strategy_weights": dict(self._state["strategy_weights"]),
        }

    def tracked_metrics(self) -> Dict[str, Any]:
        return deepcopy(
            {
                "total_auto_executed_actions": int(self._state["total_auto_executed_actions"]),
                "successful_actions": int(self._state["successful_actions"]),
                "revenue_delta_per_action": list(self._state["revenue_delta_per_action"]),
            }
        )
