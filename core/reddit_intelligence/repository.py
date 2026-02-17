from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from core.reddit_intelligence.models import get_connection, initialize_sqlite


Signal = Dict[str, Any]


class RedditSignalRepository:
    def ensure_initialized(self) -> None:
        initialize_sqlite()

    def save_signal(self, signal_data: Signal) -> Signal:
        self.ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        payload = dict(signal_data)
        payload.setdefault("status", "pending")
        payload.setdefault("created_at", now)
        payload["updated_at"] = now

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO reddit_signals (
                    id, subreddit, post_url, post_text, detected_pain_type,
                    opportunity_score, intent_level, suggested_action,
                    generated_reply, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["subreddit"],
                    payload["post_url"],
                    payload["post_text"],
                    payload.get("detected_pain_type"),
                    payload.get("opportunity_score"),
                    payload.get("intent_level"),
                    payload.get("suggested_action"),
                    payload.get("generated_reply"),
                    payload["status"],
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            conn.commit()
        return payload

    def get_pending_signals(self, limit: int = 20) -> List[Signal]:
        self.ensure_initialized()
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM reddit_signals
                WHERE status = 'pending'
                ORDER BY opportunity_score DESC, created_at DESC
                LIMIT ?
                """,
                (max(int(limit), 0),),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_signal_status(self, signal_id: str, status: str) -> Signal | None:
        self.ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE reddit_signals
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, now, signal_id),
            )
            conn.commit()
        return self.find_signal_by_id(signal_id)

    def find_signal_by_id(self, signal_id: str) -> Signal | None:
        self.ensure_initialized()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM reddit_signals WHERE id = ?",
                (signal_id,),
            ).fetchone()
        return dict(row) if row else None
