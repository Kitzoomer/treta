from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from core.reddit_intelligence.models import ensure_reddit_signals_schema
from core.storage import Storage


Signal = Dict[str, Any]


class RedditSignalRepository:
    def __init__(self, storage: Storage | None = None):
        self.storage = storage or Storage()

    def ensure_initialized(self) -> None:
        ensure_reddit_signals_schema(self.storage.conn)

    def save_signal(self, signal_data: Signal) -> Signal:
        self.ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        payload = dict(signal_data)
        payload.setdefault("status", "pending")
        payload.setdefault("karma", 0)
        payload.setdefault("replies", 0)
        payload.setdefault("performance_score", 0)
        payload.setdefault("created_at", now)
        payload["updated_at"] = now

        with self.storage._lock:
            self.storage.conn.execute(
                """
                INSERT INTO reddit_signals (
                    id, subreddit, post_url, post_text, detected_pain_type,
                    opportunity_score, intent_level, suggested_action,
                    generated_reply, status, created_at, updated_at,
                    karma, replies, performance_score, mention_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    payload["karma"],
                    payload["replies"],
                    payload["performance_score"],
                    int(bool(payload.get("mention_used", False))),
                ),
            )
            self.storage.conn.commit()
        return payload

    def get_pending_signals(self, limit: int = 20) -> List[Signal]:
        self.ensure_initialized()
        with self.storage._lock:
            cursor = self.storage.conn.execute(
                """
                SELECT * FROM reddit_signals
                WHERE status = 'pending'
                ORDER BY opportunity_score DESC, created_at DESC
                LIMIT ?
                """,
                (max(int(limit), 0),),
            )
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def update_signal_status(self, signal_id: str, status: str) -> Signal | None:
        self.ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        with self.storage._lock:
            self.storage.conn.execute(
                """
                UPDATE reddit_signals
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, now, signal_id),
            )
            self.storage.conn.commit()
        return self.find_signal_by_id(signal_id)

    def update_feedback(self, signal_id: str, karma: int, replies: int) -> Signal | None:
        self.ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        karma_value = int(karma)
        replies_value = int(replies)
        performance_score = karma_value + (replies_value * 2)

        with self.storage._lock:
            self.storage.conn.execute(
                """
                UPDATE reddit_signals
                SET karma = ?, replies = ?, performance_score = ?, updated_at = ?
                WHERE id = ?
                """,
                (karma_value, replies_value, performance_score, now, signal_id),
            )
            self.storage.conn.commit()

        return self.find_signal_by_id(signal_id)

    def get_average_performance_by_intent(self, intent_level: str) -> float:
        self.ensure_initialized()
        with self.storage._lock:
            row = self.storage.conn.execute(
                """
                SELECT AVG(performance_score) AS avg_performance
                FROM reddit_signals
                WHERE intent_level = ?
                """,
                (intent_level,),
            ).fetchone()

        if row is None or row[0] is None:
            return 0
        return float(row[0])

    def get_average_performance_by_subreddit(self, subreddit: str) -> float:
        self.ensure_initialized()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        with self.storage._lock:
            row = self.storage.conn.execute(
                """
                SELECT AVG(performance_score) AS avg_performance
                FROM reddit_signals
                WHERE subreddit = ? AND created_at >= ?
                """,
                (subreddit, cutoff),
            ).fetchone()

        if row is None or row[0] is None:
            return 0
        return float(row[0])

    def find_signal_by_id(self, signal_id: str) -> Signal | None:
        self.ensure_initialized()
        with self.storage._lock:
            cursor = self.storage.conn.execute(
                "SELECT * FROM reddit_signals WHERE id = ?",
                (signal_id,),
            )
            row = cursor.fetchone()
            columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row)) if row else None

    def _get_mention_ratio(self, where_clause: str = "", params: tuple[Any, ...] = ()) -> float:
        self.ensure_initialized()
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        query = """
            SELECT
                COUNT(*) AS total_responses,
                SUM(CASE WHEN mention_used = 1 THEN 1 ELSE 0 END) AS mentions
            FROM reddit_signals
            WHERE created_at >= ?
        """
        query_params: tuple[Any, ...] = (week_ago, *params)

        if where_clause:
            query += f" AND {where_clause}"

        with self.storage._lock:
            row = self.storage.conn.execute(query, query_params).fetchone()

        if row is None or row[0] == 0:
            return 0

        mentions = row[1] or 0
        return float(mentions) / float(row[0])

    def get_weekly_mention_ratio(self) -> float:
        return self._get_mention_ratio()

    def get_subreddit_mention_ratio(self, subreddit: str) -> float:
        return self._get_mention_ratio(where_clause="subreddit = ?", params=(subreddit,))
