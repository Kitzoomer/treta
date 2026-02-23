from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone


class CreatorDemandValidator:
    def __init__(self, storage):
        self.storage = storage

    def validate(self):
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

            validated_at = datetime.now(timezone.utc).isoformat()
            created = []

            for pain_category, frequency, avg_urgency in grouped_rows:
                dominant_monetization_level = self._dominant_monetization_level(pain_category)
                launch_priority_score = self._calculate_launch_priority_score(
                    frequency=int(frequency),
                    avg_urgency=float(avg_urgency or 0.0),
                    monetization_level=dominant_monetization_level,
                )
                demand_strength = self._demand_strength(launch_priority_score)
                recommended_action = self._recommended_action(demand_strength)
                reasoning = (
                    f"freq={int(frequency)}, urgency={float(avg_urgency or 0.0):.2f}, "
                    f"monetization={dominant_monetization_level} => {demand_strength}"
                )

                record = {
                    "id": str(uuid.uuid4()),
                    "pain_category": pain_category,
                    "frequency": int(frequency),
                    "avg_urgency": float(avg_urgency or 0.0),
                    "monetization_level": dominant_monetization_level,
                    "demand_strength": demand_strength,
                    "launch_priority_score": launch_priority_score,
                    "recommended_action": recommended_action,
                    "reasoning": reasoning,
                    "validated_at": validated_at,
                }

                self.storage.conn.execute(
                    """
                    INSERT INTO creator_demand_validations (
                        id,
                        pain_category,
                        frequency,
                        avg_urgency,
                        monetization_level,
                        demand_strength,
                        launch_priority_score,
                        recommended_action,
                        reasoning,
                        validated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        record["pain_category"],
                        record["frequency"],
                        record["avg_urgency"],
                        record["monetization_level"],
                        record["demand_strength"],
                        record["launch_priority_score"],
                        record["recommended_action"],
                        record["reasoning"],
                        record["validated_at"],
                    ),
                )
                created.append(record)

            self.storage.conn.commit()

        return created

    def list_recent_validations(self, limit=20):
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
                    demand_strength,
                    launch_priority_score,
                    recommended_action,
                    reasoning,
                    validated_at
                FROM creator_demand_validations
                ORDER BY validated_at DESC
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
            "demand_strength",
            "launch_priority_score",
            "recommended_action",
            "reasoning",
            "validated_at",
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

    def _calculate_launch_priority_score(self, *, frequency: int, avg_urgency: float, monetization_level: str) -> float:
        base = min(frequency / 20, 1.0)
        urgency_weight = avg_urgency
        monetization_weight_map = {"low": 0.4, "medium": 0.7, "high": 1.0}
        monetization_weight = monetization_weight_map.get(monetization_level, 0.4)
        return (base * 0.4) + (urgency_weight * 0.3) + (monetization_weight * 0.3)

    def _demand_strength(self, score: float) -> str:
        if score >= 0.7:
            return "strong"
        if score >= 0.4:
            return "moderate"
        return "weak"

    def _recommended_action(self, demand_strength: str) -> str:
        action_map = {
            "strong": "launch_now",
            "moderate": "test_with_post",
            "weak": "ignore",
        }
        return action_map.get(demand_strength, "ignore")

    def _ensure_schema(self):
        self.storage.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS creator_demand_validations (
                id TEXT PRIMARY KEY,
                pain_category TEXT NOT NULL,
                frequency INTEGER NOT NULL,
                avg_urgency REAL NOT NULL,
                monetization_level TEXT NOT NULL,
                demand_strength TEXT NOT NULL,
                launch_priority_score REAL NOT NULL,
                recommended_action TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                validated_at TEXT NOT NULL
            )
            """
        )
