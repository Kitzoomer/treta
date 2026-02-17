from __future__ import annotations

from typing import Any, Dict, Tuple

from core.reddit_intelligence.service import RedditIntelligenceService


class RedditIntelligenceRouter:
    def __init__(self, service: RedditIntelligenceService | None = None):
        self.service = service or RedditIntelligenceService()

    def handle_get(self, path: str, query: Dict[str, list[str]]) -> Tuple[int, Dict[str, Any]] | None:
        if path != "/reddit/signals":
            return None

        raw_limit = (query.get("limit") or ["20"])[0]
        limit = int(raw_limit)
        items = self.service.list_top_pending(limit=limit)
        return 200, {"items": items}

    def handle_post(self, path: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]] | None:
        if path != "/reddit/signals":
            return None

        subreddit = str(payload.get("subreddit", "")).strip()
        post_url = str(payload.get("post_url", "")).strip()
        post_text = str(payload.get("post_text", "")).strip()

        if not subreddit or not post_url or not post_text:
            return 400, {"ok": False, "error": "missing_required_fields"}

        signal = self.service.analyze_post(
            subreddit=subreddit,
            post_text=post_text,
            post_url=post_url,
        )
        return 200, signal

    def handle_patch(self, path: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]] | None:
        marker = "/reddit/signals/"
        suffix = "/status"
        if not path.startswith(marker) or not path.endswith(suffix):
            return None

        signal_id = path[len(marker):-len(suffix)].strip()
        status = str(payload.get("status", "")).strip()
        if not signal_id:
            return 400, {"ok": False, "error": "missing_id"}

        if status not in {"approved", "rejected", "published"}:
            return 400, {"ok": False, "error": "invalid_status"}

        updated = self.service.update_status(signal_id=signal_id, status=status)
        if updated is None:
            return 404, {"ok": False, "error": "not_found"}
        return 200, updated
