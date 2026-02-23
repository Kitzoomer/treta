from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone


class CreatorPainClassifier:
    def __init__(self, storage):
        self.storage = storage

    def classify_signal(self, signal: dict) -> dict:
        """
        Devuelve:
        {
            "pain_category": "...",
            "monetization_level": "low|medium|high",
            "urgency_score": float
        }
        """
        text = str(signal.get("post_text", "")).lower()

        category = self._detect_pain_category(text)
        urgency_score = self._calculate_urgency_score(text)
        monetization_level = self._detect_monetization_level(text)

        return {
            "pain_category": category,
            "monetization_level": monetization_level,
            "urgency_score": urgency_score,
        }

    def analyze_unprocessed_signals(self, limit=50):
        safe_limit = max(1, int(limit))
        self._ensure_schema()

        with self.storage._lock:
            cursor = self.storage.conn.execute(
                """
                SELECT rs.id, rs.post_text
                FROM reddit_signals rs
                LEFT JOIN creator_pain_analysis cpa ON cpa.reddit_signal_id = rs.id
                WHERE cpa.reddit_signal_id IS NULL
                ORDER BY rs.created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            )
            rows = cursor.fetchall()

            inserted = []
            now = datetime.now(timezone.utc).isoformat()
            for signal_id, post_text in rows:
                signal = {"id": signal_id, "post_text": post_text}
                classified = self.classify_signal(signal)
                analysis_id = str(uuid.uuid4())
                self.storage.conn.execute(
                    """
                    INSERT INTO creator_pain_analysis (
                        id,
                        reddit_signal_id,
                        pain_category,
                        monetization_level,
                        urgency_score,
                        analyzed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis_id,
                        signal_id,
                        classified.get("pain_category"),
                        classified.get("monetization_level"),
                        float(classified.get("urgency_score", 0.0)),
                        now,
                    ),
                )
                inserted.append(
                    {
                        "id": analysis_id,
                        "reddit_signal_id": signal_id,
                        **classified,
                        "analyzed_at": now,
                    }
                )

            self.storage.conn.commit()

        return inserted

    def list_recent_analysis(self, limit=50):
        safe_limit = max(1, int(limit))
        self._ensure_schema()
        with self.storage._lock:
            cursor = self.storage.conn.execute(
                """
                SELECT
                    id,
                    reddit_signal_id,
                    pain_category,
                    monetization_level,
                    urgency_score,
                    analyzed_at
                FROM creator_pain_analysis
                ORDER BY analyzed_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            )
            rows = cursor.fetchall()

        keys = [
            "id",
            "reddit_signal_id",
            "pain_category",
            "monetization_level",
            "urgency_score",
            "analyzed_at",
        ]
        return [dict(zip(keys, row)) for row in rows]

    def _ensure_schema(self):
        self.storage.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS creator_pain_analysis (
                id TEXT PRIMARY KEY,
                reddit_signal_id TEXT NOT NULL,
                pain_category TEXT,
                monetization_level TEXT,
                urgency_score REAL,
                analyzed_at TEXT NOT NULL
            )
            """
        )

    def _detect_pain_category(self, text: str) -> str:
        category_patterns = (
            ("brand_deals", [r"\bbrand deals?\b"]),
            ("pricing", [r"\bpricing\b", r"\bcharge\b", r"\brate\b", r"\brates\b"]),
            ("negotiation", [r"\bnegotiate\b", r"\bcontract\b", r"\bcontracts\b"]),
            ("retainers", [r"\bretainer\b", r"\bretainers\b"]),
            ("media_kit", [r"\bmedia kit\b"]),
            ("inconsistent_income", [r"\bpaid\b", r"\bincome inconsistent\b"]),
        )

        for name, patterns in category_patterns:
            if any(re.search(pattern, text) for pattern in patterns):
                return name
        return "other"

    def _calculate_urgency_score(self, text: str) -> float:
        urgent_patterns = [
            r"\bdesperate\b",
            r"\burgent\b",
            r"\bneed help\b",
            r"\basap\b",
            r"\bstruggling\b",
        ]
        if any(re.search(pattern, text) for pattern in urgent_patterns):
            return 0.85
        return 0.35

    def _detect_monetization_level(self, text: str) -> str:
        explicit_money_patterns = [
            r"\$\s*\d+",
            r"\b\d+\s*(usd|eur|dollars?|euros?)\b",
            r"\bpaid\b",
            r"\bincome\b",
            r"\brevenue\b",
            r"\bearnings\b",
        ]
        brand_patterns = [r"\bbrand\b", r"\bbrands\b", r"\bsponsor\b", r"\bsponsorship\b"]
        growth_patterns = [r"\bgrowth\b", r"\bfollowers\b", r"\baudience\b", r"\breach\b"]

        if any(re.search(pattern, text) for pattern in explicit_money_patterns):
            return "high"
        if any(re.search(pattern, text) for pattern in brand_patterns):
            return "medium"
        if any(re.search(pattern, text) for pattern in growth_patterns):
            return "low"
        return "low"
