from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, Iterable, List, Optional
import re

from core.events import Event


@dataclass
class Opportunity:
    source: str
    type: str
    title: str
    description: str
    score: float
    reasons: List[str]
    importance_level: str
    suggested_actions: List[str]
    timestamp: str


class OpportunityEngine:
    """
    Lightweight and testable opportunity detector.

    - Evaluates raw events from supported sensors
    - Builds and scores candidate opportunities
    - Filters by score, duplicate title similarity and user goals
    - Stores accepted opportunities in memory
    - Emits OpportunityDetected events through EventBus when available
    """

    SUPPORTED_EVENTS = {
        "EmailFetched",
        "ForumPostFetched",
        "MetricsUpdate",
        "DailyContext",
    }

    def __init__(
        self,
        event_bus: Optional[Any] = None,
        semantic_analyzer: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        goals_provider: Optional[Callable[[], Iterable[str]]] = None,
        min_score: float = 0.45,
        duplicate_similarity_threshold: float = 0.9,
    ):
        self.event_bus = event_bus
        self.semantic_analyzer = semantic_analyzer or self._default_semantic_analysis
        self.goals_provider = goals_provider
        self.min_score = min_score
        self.duplicate_similarity_threshold = duplicate_similarity_threshold

        self._opportunities: List[Opportunity] = []
        self._candidates: List[Opportunity] = []

    def evaluate_signal(self, event: Any) -> Optional[Opportunity]:
        """Process a raw event and return accepted opportunity, if any."""
        normalized_event = self._normalize_event(event)
        event_type = normalized_event.get("type", "")
        if event_type not in self.SUPPORTED_EVENTS:
            return None

        normalized_text = self._normalize_text(self._extract_text(normalized_event.get("payload", {})))
        analysis = self.semantic_analyzer(
            {
                "event_type": event_type,
                "source": normalized_event.get("source", "unknown"),
                "payload": normalized_event.get("payload", {}),
                "normalized_text": normalized_text,
            }
        )

        candidate = self._build_candidate(normalized_event, normalized_text, analysis)
        candidate.score = self.score_opportunity(candidate)
        self._candidates.append(candidate)

        passed = self.filter_opportunities([candidate])
        if not passed:
            return None

        accepted = passed[0]
        self._opportunities.append(accepted)
        self._emit_opportunity_detected(accepted)
        return accepted

    def score_opportunity(self, candidate: Opportunity) -> float:
        """Return a score from 0 to 1."""
        text = f"{candidate.title} {candidate.description}".lower()
        reasons_weight = min(len(candidate.reasons) * 0.08, 0.32)

        keyword_bonus = 0.0
        for kw, weight in {
            "lead": 0.12,
            "urgent": 0.12,
            "sale": 0.10,
            "client": 0.10,
            "offer": 0.08,
            "problem": 0.08,
            "growth": 0.08,
            "revenue": 0.12,
            "automation": 0.10,
        }.items():
            if kw in text:
                keyword_bonus += weight

        goals_bonus = 0.0
        goals = self._get_user_goals()
        if goals:
            title_and_description = f"{candidate.title} {candidate.description}".lower()
            overlaps = sum(1 for goal in goals if goal in title_and_description)
            goals_bonus = min(overlaps * 0.12, 0.24)

        base = 0.30
        score = base + reasons_weight + min(keyword_bonus, 0.35) + goals_bonus
        return max(0.0, min(1.0, round(score, 4)))

    def filter_opportunities(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        """Filter candidates by score, title similarity and goals relevance."""
        filtered: List[Opportunity] = []
        goals = self._get_user_goals()

        for opp in opportunities:
            if opp.score < self.min_score:
                continue
            if self._is_duplicate_title(opp.title):
                continue
            if goals and not self._matches_goals(opp, goals):
                continue
            filtered.append(opp)

        return filtered

    def generate_reports(self) -> Dict[str, Any]:
        """Generate a structured report for dashboards/voice/text output."""
        opportunities_sorted = sorted(self._opportunities, key=lambda o: o.score, reverse=True)
        by_source: Dict[str, int] = {}
        for opp in opportunities_sorted:
            by_source[opp.source] = by_source.get(opp.source, 0) + 1

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "total_candidates": len(self._candidates),
            "total_detected": len(self._opportunities),
            "top_opportunities": [asdict(opp) for opp in opportunities_sorted[:5]],
            "by_source": by_source,
        }

    def get_top_opportunities(self, n: int) -> List[Opportunity]:
        return sorted(self._opportunities, key=lambda o: o.score, reverse=True)[: max(0, n)]

    def poll_event_bus(self, timeout: float = 0.1) -> Optional[Opportunity]:
        """Listen once to the configured EventBus (if injected)."""
        if self.event_bus is None:
            return None

        event = self.event_bus.pop(timeout=timeout)
        if event is None:
            return None
        return self.evaluate_signal(event)

    def _normalize_event(self, event: Any) -> Dict[str, Any]:
        if isinstance(event, Event):
            return {
                "type": event.type,
                "payload": event.payload,
                "source": event.source,
                "timestamp": event.timestamp,
            }
        if isinstance(event, dict):
            return {
                "type": event.get("type", ""),
                "payload": event.get("payload", {}),
                "source": event.get("source", "unknown"),
                "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
            }
        raise ValueError("Unsupported event type for evaluate_signal")

    def _extract_text(self, payload: Dict[str, Any]) -> str:
        text_parts = []
        preferred_fields = [
            "subject",
            "title",
            "snippet",
            "description",
            "content",
            "summary",
            "text",
        ]
        for field_name in preferred_fields:
            value = payload.get(field_name)
            if isinstance(value, str) and value.strip():
                text_parts.append(value)

        if not text_parts:
            # Fallback: flatten simple payload values.
            for value in payload.values():
                if isinstance(value, str):
                    text_parts.append(value)
                elif isinstance(value, (int, float)):
                    text_parts.append(str(value))

        return " ".join(text_parts)

    def _normalize_text(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^a-z0-9áéíóúñü\s\-.,:;!?]", "", text)
        return text

    def _build_candidate(
        self,
        event: Dict[str, Any],
        normalized_text: str,
        analysis: Dict[str, Any],
    ) -> Opportunity:
        payload = event.get("payload", {})
        title = (
            analysis.get("title")
            or payload.get("subject")
            or payload.get("title")
            or f"Opportunity from {event.get('type', 'event')}"
        )
        description = analysis.get("description") or normalized_text[:280]
        reasons = analysis.get("reasons") or ["semantic_relevance_detected"]
        suggested_actions = analysis.get("suggested_actions") or ["Review and decide next action"]

        score_hint = analysis.get("score_hint")
        initial_score = 0.0
        if isinstance(score_hint, (int, float)):
            initial_score = max(0.0, min(float(score_hint), 1.0))

        return Opportunity(
            source=event.get("source", "unknown"),
            type=event.get("type", "unknown"),
            title=title,
            description=description,
            score=initial_score,
            reasons=[str(r) for r in reasons],
            importance_level=self._importance_from_score(initial_score),
            suggested_actions=[str(a) for a in suggested_actions],
            timestamp=event.get("timestamp", datetime.utcnow().isoformat()),
        )

    def _emit_opportunity_detected(self, opportunity: Opportunity):
        opportunity.importance_level = self._importance_from_score(opportunity.score)
        if self.event_bus is None:
            return

        self.event_bus.push(
            Event(
                type="OpportunityDetected",
                payload={
                    "source": opportunity.source,
                    "title": opportunity.title,
                    "why": opportunity.reasons,
                    "score": opportunity.score,
                },
                source="opportunity_engine",
            )
        )

    def _is_duplicate_title(self, title: str) -> bool:
        normalized_title = self._normalize_text(title)
        for existing in self._opportunities:
            ratio = SequenceMatcher(
                None,
                normalized_title,
                self._normalize_text(existing.title),
            ).ratio()
            if ratio >= self.duplicate_similarity_threshold:
                return True
        return False

    def _importance_from_score(self, score: float) -> str:
        if score >= 0.8:
            return "high"
        if score >= 0.6:
            return "medium"
        return "low"

    def _matches_goals(self, opportunity: Opportunity, goals: List[str]) -> bool:
        combined = f"{opportunity.title} {opportunity.description}".lower()
        return any(goal in combined for goal in goals)

    def _get_user_goals(self) -> List[str]:
        if not self.goals_provider:
            return []

        try:
            goals = self.goals_provider()
        except Exception:
            return []

        if goals is None:
            return []

        if isinstance(goals, str):
            return [goals.lower().strip()]

        return [str(goal).lower().strip() for goal in goals if str(goal).strip()]

    def _default_semantic_analysis(self, analysis_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Default local fallback for semantic analysis.

        Production wiring can inject a GPT/OpenClaw analyzer while tests can
        provide deterministic stubs.
        """
        text = analysis_input.get("normalized_text", "")
        event_type = analysis_input.get("event_type", "unknown")

        reasons = []
        for token in ["urgent", "lead", "client", "growth", "problem", "offer"]:
            if token in text:
                reasons.append(f"contains:{token}")

        return {
            "title": f"{event_type} signal",
            "description": text[:280],
            "reasons": reasons or ["general_signal_detected"],
            "suggested_actions": ["Validate opportunity", "Prioritize in daily plan"],
            "score_hint": 0.5 if reasons else 0.4,
        }
