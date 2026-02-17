from __future__ import annotations

from typing import Any, Dict


class RedditDailyPlanStore:
    _latest_plan: Dict[str, Any] = {}

    @classmethod
    def save(cls, plan: Dict[str, Any]) -> Dict[str, Any]:
        cls._latest_plan = dict(plan)
        return dict(cls._latest_plan)

    @classmethod
    def get_latest(cls) -> Dict[str, Any]:
        return dict(cls._latest_plan)

