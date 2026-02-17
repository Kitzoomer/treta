from __future__ import annotations

import random
import uuid
from typing import Any, Dict, List

from core.reddit_intelligence.repository import RedditSignalRepository
from core.reddit_intelligence.sales_insight import SalesInsightService


class RedditIntelligenceService:
    def __init__(self, repository: RedditSignalRepository | None = None):
        self.repository = repository or RedditSignalRepository()

    def analyze_post(self, subreddit: str, post_text: str, post_url: str) -> Dict[str, Any]:
        text_lower = post_text.lower()

        direct_keywords = ("template", "example", "anyone have", "need help")
        implicit_keywords = ("struggling", "problem", "don’t know", "don't know")

        if any(keyword in text_lower for keyword in direct_keywords):
            detected_pain_type = "direct"
            intent_level = "direct"
            opportunity_score = random.randint(80, 95)
            base_action = "value_plus_mention"
            reasoning = "Detected explicit buying/help-seeking intent in post text."
        elif any(keyword in text_lower for keyword in implicit_keywords):
            detected_pain_type = "implicit"
            intent_level = "implicit"
            opportunity_score = random.randint(50, 75)
            base_action = "value"
            reasoning = "Detected pain/problem language with indirect intent."
        else:
            detected_pain_type = "trend"
            intent_level = "trend"
            opportunity_score = random.randint(30, 60)
            base_action = "ignore"
            reasoning = "Detected general discussion without clear purchase intent."

        avg_perf = self.repository.get_average_performance_by_intent(intent_level)

        if intent_level == "direct":
            suggested_action = "value" if avg_perf < 3 else "value_plus_mention"
        elif intent_level == "implicit":
            suggested_action = "value_plus_mention" if avg_perf > 15 else "value"
        else:
            suggested_action = "ignore"

        if suggested_action != base_action:
            reasoning += " Suggested action adapted based on historical engagement performance."

        global_ratio = self.repository.get_weekly_mention_ratio()
        subreddit_ratio = self.repository.get_subreddit_mention_ratio(subreddit)

        if suggested_action == "value_plus_mention":
            if global_ratio > 0.4:
                suggested_action = "value"
                reasoning += " Global mention cap applied."
            if suggested_action == "value_plus_mention" and subreddit_ratio > 0.3:
                suggested_action = "value"
                reasoning += " Subreddit mention cap applied."

        try:
            high_performing_keywords = SalesInsightService().get_high_performing_keywords()
            if any(keyword in text_lower for keyword in high_performing_keywords):
                boost = random.randint(10, 20)
                opportunity_score = min(100, opportunity_score + boost)
                reasoning += " Boosted score due to alignment with high-performing product keywords."
        except Exception:
            pass

        generated_reply = self._build_reply(suggested_action, subreddit)

        signal = {
            "id": str(uuid.uuid4()),
            "subreddit": subreddit,
            "post_url": post_url,
            "post_text": post_text,
            "detected_pain_type": detected_pain_type,
            "opportunity_score": opportunity_score,
            "intent_level": intent_level,
            "suggested_action": suggested_action,
            "generated_reply": generated_reply,
            "reasoning": reasoning,
            "mention_used": suggested_action == "value_plus_mention",
        }
        return self.repository.save_signal(signal)

    def list_top_pending(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.repository.get_pending_signals(limit=limit)

    def update_status(self, signal_id: str, status: str) -> Dict[str, Any] | None:
        return self.repository.update_signal_status(signal_id=signal_id, status=status)

    def update_feedback(self, signal_id: str, karma: int, replies: int) -> Dict[str, Any] | None:
        return self.repository.update_feedback(signal_id=signal_id, karma=karma, replies=replies)

    def _build_reply(self, suggested_action: str, subreddit: str) -> str:
        if suggested_action == "value_plus_mention":
            return (
                f"Tu enfoque va bien. Para avanzar rápido, divide el problema en 3 pasos, "
                f"itera con feedback real y documenta lo que funciona. "
                f"Si te sirve, en Treta usamos una plantilla corta para convertir caos en plan accionable "
                f"sin perder contexto en r/{subreddit}."
            )
        if suggested_action == "value":
            return (
                "Prueba una mini-rutina: define objetivo, identifica cuello de botella principal "
                "y ejecuta un experimento de 24 horas con una métrica clara. "
                "Eso suele desbloquear más que buscar la solución perfecta."
            )
        return "He visto este patrón repetirse; recopilar ejemplos y comparar enfoques suele aportar claridad útil."
