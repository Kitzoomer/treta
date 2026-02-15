from __future__ import annotations

import re
from typing import Any, Dict


class RiskEvaluationEngine:
    """Assigns deterministic risk metadata to strategy actions."""

    _SALES_PATTERN = re.compile(r"(\d+)\s+sales")

    def _extract_sales(self, action: Dict[str, Any]) -> int:
        raw_sales = action.get("sales")
        if raw_sales is not None:
            try:
                return max(int(raw_sales), 0)
            except (TypeError, ValueError):
                return 0

        reasoning = str(action.get("reasoning") or "")
        match = self._SALES_PATTERN.search(reasoning)
        if match is None:
            return 0
        return int(match.group(1))

    def evaluate(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = str(action.get("type") or "").strip()
        sales = self._extract_sales(action)

        if action_type == "scale" and sales >= 5:
            risk_level = "low"
            expected_impact_score = 8
        elif action_type == "price_test":
            risk_level = "low"
            expected_impact_score = 6
        elif action_type == "review":
            risk_level = "medium"
            expected_impact_score = 5
        elif action_type == "new_product":
            risk_level = "medium"
            expected_impact_score = 7
        elif action_type == "archive":
            risk_level = "high"
            expected_impact_score = 4
        else:
            risk_level = "medium"
            expected_impact_score = 5

        return {
            "risk_level": risk_level,
            "expected_impact_score": expected_impact_score,
            "auto_executable": risk_level == "low",
        }

