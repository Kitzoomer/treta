from __future__ import annotations

import json
from typing import Any

from core.model_policy_engine import ModelPolicyEngine


class StrategicSnapshotEngine:
    """Generate compact strategic state summaries for long-term memory compression."""

    def __init__(self, gpt_client_optional: Any = None, model_policy_engine: ModelPolicyEngine | None = None):
        self._gpt_client = gpt_client_optional
        self._model_policy_engine = model_policy_engine or ModelPolicyEngine()

    def _fallback_snapshot(self, full_state: dict) -> str:
        opportunities = full_state.get("active_opportunities", [])
        strategies = full_state.get("current_strategies", [])
        pending_actions = full_state.get("pending_actions", [])
        active_risks = full_state.get("active_risks", [])

        sections = [
            f"Oportunidades activas ({len(opportunities)}): " + "; ".join(str(item) for item in opportunities[:5]),
            f"Estrategias actuales ({len(strategies)}): " + "; ".join(str(item) for item in strategies[:5]),
            f"Acciones pendientes ({len(pending_actions)}): " + "; ".join(str(item) for item in pending_actions[:6]),
            f"Riesgos activos ({len(active_risks)}): " + "; ".join(str(item) for item in active_risks[:5]),
        ]
        return "\n".join(sections).strip()[:3200]

    def generate_snapshot(self, full_state: dict) -> str:
        if not isinstance(full_state, dict):
            return ""

        if self._gpt_client is None or not hasattr(self._gpt_client, "chat"):
            return self._fallback_snapshot(full_state)

        prompt = (
            "Genera un Strategic Snapshot ultra-compacto (<=500 tokens aprox) en español. "
            "Incluye SOLO: oportunidades activas, estrategias actuales, acciones pendientes y riesgos activos. "
            "No inventes datos y evita redundancia."
        )
        payload = json.dumps(full_state, ensure_ascii=False)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Estado completo:\n{payload}"},
        ]
        model_name = self._model_policy_engine.get_model(task_type="planning")
        try:
            return str(self._gpt_client.chat(messages, task_type="planning", model=model_name)).strip()
        except TypeError:
            try:
                return str(self._gpt_client.chat(messages, task_type="planning")).strip()
            except Exception:
                return self._fallback_snapshot(full_state)
        except Exception:
            return self._fallback_snapshot(full_state)

