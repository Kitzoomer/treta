from __future__ import annotations

from typing import Any, Dict

from core.agents.base_agent import BaseAgent
from core.product_launch_store import ProductLaunchStore
from core.strategy_engine import StrategyEngine


class GrowthAgent(BaseAgent):
    PROMPT_VERSION = "growth.v1"
    SYSTEM_PROMPT = "Eres GrowthAgent. Identifica oportunidades de crecimiento basadas en performance histórico."

    def __init__(self, product_launch_store: ProductLaunchStore):
        super().__init__(
            name="growth_agent",
            role_description="Genera recomendaciones de crecimiento por producto y categoría.",
            allowed_tools=["strategy_engine.generate_recommendations"],
            model_type="analytics",
        )
        self._strategy_engine = StrategyEngine(product_launch_store=product_launch_store)

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        del input_data
        recommendations = self._strategy_engine.generate_recommendations()
        return {
            "agent": self.name,
            "prompt_version": self.PROMPT_VERSION,
            "system_prompt": self.SYSTEM_PROMPT,
            "recommendations": recommendations,
        }
