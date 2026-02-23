from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone


class CreatorProductSuggester:
    def __init__(self, storage):
        self.storage = storage

    def generate_suggestions(self):
        self._ensure_schema()

        with self.storage._lock:
            cursor = self.storage.conn.execute(
                """
                SELECT
                    pain_category,
                    COUNT(*) AS frequency,
                    AVG(COALESCE(urgency_score, 0.0)) AS avg_urgency
                FROM creator_pain_analysis
                WHERE pain_category IS NOT NULL
                GROUP BY pain_category
                ORDER BY frequency DESC
                """
            )
            grouped_rows = cursor.fetchall()

            generated_at = datetime.now(timezone.utc).isoformat()
            created = []

            for pain_category, frequency, avg_urgency in grouped_rows:
                monetization_level = self._dominant_monetization_level(pain_category)
                suggestion = {
                    "id": str(uuid.uuid4()),
                    "pain_category": pain_category,
                    "frequency": int(frequency),
                    "avg_urgency": float(avg_urgency or 0.0),
                    "monetization_level": monetization_level,
                    "suggested_product": self._suggested_product_for(pain_category),
                    "positioning_angle": self._positioning_angle_for(pain_category),
                    "estimated_price_range": self._estimated_price_range_for(monetization_level),
                    "generated_at": generated_at,
                }

                self.storage.conn.execute(
                    """
                    INSERT INTO creator_product_suggestions (
                        id,
                        pain_category,
                        frequency,
                        avg_urgency,
                        monetization_level,
                        suggested_product,
                        positioning_angle,
                        estimated_price_range,
                        generated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        suggestion["id"],
                        suggestion["pain_category"],
                        suggestion["frequency"],
                        suggestion["avg_urgency"],
                        suggestion["monetization_level"],
                        suggestion["suggested_product"],
                        suggestion["positioning_angle"],
                        suggestion["estimated_price_range"],
                        suggestion["generated_at"],
                    ),
                )
                created.append(suggestion)

            self.storage.conn.commit()

        return created

    def list_recent_suggestions(self, limit=20):
        safe_limit = max(1, int(limit))
        self._ensure_schema()
        with self.storage._lock:
            cursor = self.storage.conn.execute(
                """
                SELECT
                    id,
                    pain_category,
                    frequency,
                    avg_urgency,
                    monetization_level,
                    suggested_product,
                    positioning_angle,
                    estimated_price_range,
                    generated_at
                FROM creator_product_suggestions
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            )
            rows = cursor.fetchall()

        keys = [
            "id",
            "pain_category",
            "frequency",
            "avg_urgency",
            "monetization_level",
            "suggested_product",
            "positioning_angle",
            "estimated_price_range",
            "generated_at",
        ]
        return [dict(zip(keys, row)) for row in rows]

    def _dominant_monetization_level(self, pain_category: str) -> str:
        cursor = self.storage.conn.execute(
            """
            SELECT monetization_level
            FROM creator_pain_analysis
            WHERE pain_category = ? AND monetization_level IS NOT NULL
            """,
            (pain_category,),
        )
        levels = [row[0] for row in cursor.fetchall() if row[0]]
        if not levels:
            return "low"
        return Counter(levels).most_common(1)[0][0]

    def _suggested_product_for(self, pain_category: str) -> str:
        product_map = {
            "pricing": "Pricing Calculator + Rate Guide",
            "negotiation": "Negotiation Script Pack",
            "brand_deals": "Advanced Brand Deal Kit",
            "retainers": "Retainer System Framework",
            "inconsistent_income": "Creator Income Stabilization Blueprint",
        }
        return product_map.get(pain_category, "Creator Revenue Optimization Toolkit")

    def _estimated_price_range_for(self, monetization_level: str) -> str:
        if monetization_level == "low":
            return "19-29"
        if monetization_level == "medium":
            return "29-59"
        return "59-149"

    def _positioning_angle_for(self, pain_category: str) -> str:
        angle_map = {
            "pricing": "Charge confidently using benchmark-backed creator rates.",
            "negotiation": "Close better deals with proven negotiation language.",
            "brand_deals": "Systemize brand deals with premium-ready templates.",
            "retainers": "Turn one-off projects into stable retainer income.",
            "inconsistent_income": "Build predictable monthly income from creator work.",
        }
        return angle_map.get(pain_category, "Convert creator pain into repeatable revenue systems.")

    def _ensure_schema(self):
        self.storage.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS creator_product_suggestions (
                id TEXT PRIMARY KEY,
                pain_category TEXT NOT NULL,
                frequency INTEGER NOT NULL,
                avg_urgency REAL NOT NULL,
                monetization_level TEXT NOT NULL,
                suggested_product TEXT NOT NULL,
                positioning_angle TEXT,
                estimated_price_range TEXT,
                generated_at TEXT NOT NULL
            )
            """
        )
