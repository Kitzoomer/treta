from __future__ import annotations

from typing import Any, Dict


class AlignmentEngine:
    """Evaluate strategic fit before proposal generation."""

    _AUDIENCE_KEYWORDS = (
        "service",
        "services",
        "professional",
        "professionals",
        "creator",
        "creators",
        "freelancer",
        "freelancers",
        "coach",
        "coaches",
    )
    _TYPE_KEYWORDS = ("template", "system", "kit")
    _PROBLEM_KEYWORDS = (
        "revenue",
        "client acquisition",
        "clients",
        "sales",
        "automation",
        "automate",
    )

    def evaluate(self, opportunity: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = context or {}

        score = 0
        reasons: list[str] = []

        opportunity_text = self._build_text(opportunity)
        opportunity_data = opportunity.get("opportunity", {}) if isinstance(opportunity, dict) else {}

        if self._contains_any(opportunity_text, self._AUDIENCE_KEYWORDS):
            score += 20
            reasons.append("Audience matches service professionals/creators")

        if self._contains_any(opportunity_text, self._TYPE_KEYWORDS):
            score += 20
            reasons.append("Opportunity type fits template/system/kit")

        if self._contains_any(opportunity_text, self._PROBLEM_KEYWORDS):
            score += 20
            reasons.append("Problem relates to revenue/client acquisition/automation")

        confidence = self._extract_confidence(opportunity_data)
        if confidence >= 7:
            score += 20
            reasons.append("Confidence score is at least 7")

        if self._has_distraction_tag(opportunity):
            score -= 20
            reasons.append("Tagged as distraction/non-core")

        if self._is_too_similar(opportunity_text, context.get("recent_proposals", [])):
            score -= 20
            reasons.append("Too similar to recently generated proposal")

        score = max(0, min(100, float(score)))
        aligned = score >= 60

        if not reasons:
            reasons.append("No strategic alignment signals found")

        return {
            "aligned": aligned,
            "alignment_score": score,
            "reason": "; ".join(reasons),
        }

    def _build_text(self, opportunity: Dict[str, Any]) -> str:
        return " ".join(
            [
                str(opportunity.get("title", "")),
                str(opportunity.get("summary", "")),
                str(opportunity.get("context", "")),
            ]
        ).lower()

    def _extract_confidence(self, opportunity_data: Dict[str, Any]) -> float:
        value = opportunity_data.get("confidence", opportunity_data.get("confidence_score"))
        if value is None:
            value = opportunity_data.get("money", opportunity_data.get("growth", 0))
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _has_distraction_tag(self, opportunity: Dict[str, Any]) -> bool:
        tags = opportunity.get("tags", [])
        if not isinstance(tags, list):
            return False
        normalized = {str(tag).strip().lower() for tag in tags}
        return bool(normalized & {"distraction", "non-core", "non_core"})

    def _is_too_similar(self, opportunity_text: str, recent_proposals: list[Dict[str, Any]]) -> bool:
        if not opportunity_text.strip():
            return False

        tokens = {token for token in opportunity_text.split() if len(token) > 3}
        if not tokens:
            return False

        for proposal in recent_proposals:
            existing_text = " ".join(
                [
                    str(proposal.get("product_name", "")),
                    str(proposal.get("product_type", "")),
                    str(proposal.get("target_audience", "")),
                    str(proposal.get("core_problem", "")),
                    str(proposal.get("solution", "")),
                ]
            ).lower()
            existing_tokens = {token for token in existing_text.split() if len(token) > 3}
            if not existing_tokens:
                continue
            overlap = len(tokens & existing_tokens)
            similarity = overlap / max(1, min(len(tokens), len(existing_tokens)))
            if similarity >= 0.5:
                return True

        return False

    def _contains_any(self, text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)
