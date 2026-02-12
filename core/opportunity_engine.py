from __future__ import annotations

from typing import Dict, List


class OpportunityEngine:
    """Generate deterministic DecisionEngine-ready opportunities from research signals.

    This module transforms external research items into a normalized opportunity shape
    so Treta can evaluate them through autonomy policy layers without coupling to I/O.
    """

    def generate_opportunities(self, research_data: List[Dict]) -> List[Dict]:
        opportunities: List[Dict] = []

        for item in research_data:
            engagement = int(item.get("engagement", 0))
            title = str(item.get("title", "")).strip()
            summary = str(item.get("summary", "")).strip()
            source = str(item.get("source", "")).strip() or "unknown"

            money, growth = self._money_growth_from_engagement(engagement)
            energy = self._energy_from_execution_cost(title, summary)
            risk = self._risk_from_source(source)

            opportunity = {
                "money": money,
                "growth": growth,
                "energy": energy,
                "health": 0,
                "relationships": 0,
                "risk": risk,
                "source": source,
                "context": f"{title}: {summary}".strip(": "),
            }
            opportunities.append(opportunity)

        return opportunities

    def _money_growth_from_engagement(self, engagement: int) -> tuple[int, int]:
        if engagement >= 80:
            return 9, 8
        if engagement >= 50:
            return 7, 6
        if engagement >= 20:
            return 5, 4
        return 3, 2

    def _energy_from_execution_cost(self, title: str, summary: str) -> int:
        text = f"{title} {summary}".lower()
        length = len(text)

        keyword_cost = 0
        for token, weight in {
            "build": 2,
            "setup": 2,
            "integration": 2,
            "migration": 3,
            "manual": 1,
            "complex": 2,
        }.items():
            if token in text:
                keyword_cost += weight

        length_cost = 1 if length < 120 else 3 if length < 260 else 5
        return min(10, max(1, length_cost + keyword_cost))

    def _risk_from_source(self, source: str) -> int:
        normalized = source.lower().strip()
        trusted_sources = {
            "gmail",
            "forum",
            "reddit",
            "x",
            "twitter",
            "linkedin",
            "github",
            "hn",
            "hackernews",
            "newsletter",
        }

        if normalized in trusted_sources:
            return 3
        if normalized in {"", "unknown", "n/a", "none"}:
            return 8
        return 6
