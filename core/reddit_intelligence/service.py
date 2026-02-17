from __future__ import annotations

import random
import uuid
from typing import Any, Dict, List

from core.reddit_intelligence.repository import RedditSignalRepository


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
            suggested_action = "value_plus_mention"
        elif any(keyword in text_lower for keyword in implicit_keywords):
            detected_pain_type = "implicit"
            intent_level = "implicit"
            opportunity_score = random.randint(50, 75)
            suggested_action = "value"
        else:
            detected_pain_type = "trend"
            intent_level = "trend"
            opportunity_score = random.randint(30, 60)
            suggested_action = "ignore"

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
        }
        return self.repository.save_signal(signal)

    def list_top_pending(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.repository.get_pending_signals(limit=limit)

    def update_status(self, signal_id: str, status: str) -> Dict[str, Any] | None:
        return self.repository.update_signal_status(signal_id=signal_id, status=status)

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
