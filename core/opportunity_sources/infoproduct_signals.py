from __future__ import annotations

from typing import Any, Dict, List

from core.events import Event


class InfoproductSignals:
    """Deterministic simulated source of infoproduct opportunities."""

    def generate_signals(self) -> List[Dict[str, Any]]:
        return [
            {
                "title": "Creators asking for TikTok brand collaboration media kit template",
                "summary": "Multiple creators are requesting editable media kit templates to pitch brand collaborations on TikTok.",
                "opportunity": {
                    "money": 8,
                    "growth": 7,
                    "energy": 6,
                    "health": 7,
                    "relationships": 8,
                    "risk": 3,
                },
            },
            {
                "title": "Coaches struggling with automated onboarding systems",
                "summary": "Independent coaches report friction setting up onboarding automations for new clients.",
                "opportunity": {
                    "money": 7,
                    "growth": 8,
                    "energy": 5,
                    "health": 6,
                    "relationships": 7,
                    "risk": 4,
                },
            },
            {
                "title": "Freelancers asking for client proposal templates",
                "summary": "Freelancers ask for polished proposal templates that improve close rates and reduce writing time.",
                "opportunity": {
                    "money": 9,
                    "growth": 6,
                    "energy": 7,
                    "health": 7,
                    "relationships": 6,
                    "risk": 2,
                },
            },
        ]

    def emit_signals(self, bus) -> None:
        for signal in self.generate_signals():
            bus.push(
                Event(
                    type="OpportunityDetected",
                    payload={
                        "source": "simulated_forum",
                        "title": signal["title"],
                        "summary": signal["summary"],
                        "opportunity": signal["opportunity"],
                    },
                    source="infoproduct_signals",
                )
            )
