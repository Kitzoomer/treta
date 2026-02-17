from __future__ import annotations

from typing import Any, Dict, Tuple

from core.reddit_intelligence.daily_plan_store import RedditDailyPlanStore
from core.reddit_intelligence.service import RedditIntelligenceService


class RedditIntelligenceRouter:
    def __init__(self, service: RedditIntelligenceService | None = None):
        self._service = service

    def _service_instance(self) -> RedditIntelligenceService:
        if self._service is None:
            self._service = RedditIntelligenceService()
        return self._service

    def handle_get(self, path: str, query: Dict[str, list[str]]) -> Tuple[int, Any] | None:
        if path == "/reddit/signals":
            raw_limit = (query.get("limit") or ["20"])[0]
            limit = int(raw_limit)
            items = self._service_instance().list_top_pending(limit=limit)
            return 200, {"items": items}

        if path == "/reddit/daily_actions":
            raw_limit = (query.get("limit") or ["5"])[0]
            limit = int(raw_limit)
            items = self._service_instance().get_daily_top_actions(limit=limit)
            return 200, items

        if path == "/reddit/today_plan":
            return 200, RedditDailyPlanStore.get_latest()

        return None

    def handle_post(self, path: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]] | None:
        if path != "/reddit/signals":
            return None

        subreddit = str(payload.get("subreddit", "")).strip()
        post_url = str(payload.get("post_url", "")).strip()
        post_text = str(payload.get("post_text", "")).strip()

        if not subreddit or not post_url or not post_text:
            return 400, {"ok": False, "error": "missing_required_fields"}

        signal = self._service_instance().analyze_post(
            subreddit=subreddit,
            post_text=post_text,
            post_url=post_url,
        )
        return 200, signal

    def handle_patch(self, path: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]] | None:
        marker = "/reddit/signals/"
        if not path.startswith(marker):
            return None

        status_suffix = "/status"
        feedback_suffix = "/feedback"

        if path.endswith(status_suffix):
            signal_id = path[len(marker):-len(status_suffix)].strip()
            status = str(payload.get("status", "")).strip()
            if not signal_id:
                return 400, {"ok": False, "error": "missing_id"}

            if status not in {"approved", "rejected", "published"}:
                return 400, {"ok": False, "error": "invalid_status"}

            updated = self._service_instance().update_status(signal_id=signal_id, status=status)
            if updated is None:
                return 404, {"ok": False, "error": "not_found"}
            return 200, updated

        if path.endswith(feedback_suffix):
            signal_id = path[len(marker):-len(feedback_suffix)].strip()
            if not signal_id:
                return 400, {"ok": False, "error": "missing_id"}

            if "karma" not in payload or "replies" not in payload:
                return 400, {"ok": False, "error": "missing_feedback_fields"}

            try:
                karma = int(payload.get("karma", 0))
                replies = int(payload.get("replies", 0))
            except (TypeError, ValueError):
                return 400, {"ok": False, "error": "invalid_feedback_values"}

            updated = self._service_instance().update_feedback(
                signal_id=signal_id,
                karma=karma,
                replies=replies,
            )
            if updated is None:
                return 404, {"ok": False, "error": "not_found"}
            return 200, updated

        return None
