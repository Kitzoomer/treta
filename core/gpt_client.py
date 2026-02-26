from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pytz

from core.model_policy_engine import ModelPolicyEngine
from core.revenue_attribution.store import RevenueAttributionStore

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


@dataclass
class GPTClientConfigurationError(Exception):
    message: str
    code: str = "missing_openai_api_key"

    def __str__(self) -> str:
        return self.message


class GPTClient:
    def __init__(
        self,
        revenue_attribution_store: RevenueAttributionStore | None = None,
        openai_client: Any | None = None,
        model_policy_engine: ModelPolicyEngine | None = None,
    ):
        self._revenue_attribution_store = revenue_attribution_store
        self._model_policy_engine = model_policy_engine or ModelPolicyEngine()
        if openai_client is not None:
            self._client = openai_client
            return

        if OpenAI is None:
            raise GPTClientConfigurationError("openai package not installed")

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise GPTClientConfigurationError(message="OPENAI_API_KEY is not set")
        self._client = OpenAI(api_key=api_key)

    def _tool_spec(self) -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "Get current time in system timezone",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_system_timezone",
                    "description": "Return configured system timezone",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_revenue_summary",
                    "description": "Return revenue summary metrics",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_dominant_subreddit",
                    "description": "Return subreddit generating most revenue",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    def get_current_time(self) -> str:
        timezone_name = self.get_system_timezone()
        try:
            timezone_obj = pytz.timezone(timezone_name)
        except Exception:
            timezone_obj = pytz.timezone("UTC")
        return datetime.now(timezone_obj).strftime("%Y-%m-%d %H:%M:%S %Z")

    def get_system_timezone(self) -> str:
        return os.getenv("TRETA_TIMEZONE", "UTC").strip() or "UTC"

    def get_revenue_summary(self) -> dict[str, object]:
        if self._revenue_attribution_store is None:
            return {"totals": {"sales": 0, "revenue": 0.0}}
        summary = self._revenue_attribution_store.summary()
        totals = summary.get("totals", {}) if isinstance(summary, dict) else {}
        return {
            "totals": {
                "sales": int(totals.get("sales", 0) or 0),
                "revenue": float(totals.get("revenue", 0.0) or 0.0),
            }
        }

    def get_dominant_subreddit(self) -> dict[str, object]:
        if self._revenue_attribution_store is None:
            return {"subreddit": "", "revenue": 0.0}
        summary = self._revenue_attribution_store.summary()
        by_subreddit = summary.get("by_subreddit", {}) if isinstance(summary, dict) else {}
        if not isinstance(by_subreddit, dict) or not by_subreddit:
            return {"subreddit": "", "revenue": 0.0}
        subreddit, metrics = max(
            by_subreddit.items(),
            key=lambda row: float((row[1] or {}).get("revenue", 0.0) if isinstance(row[1], dict) else 0.0),
        )
        revenue = float(metrics.get("revenue", 0.0) or 0.0) if isinstance(metrics, dict) else 0.0
        return {"subreddit": str(subreddit), "revenue": revenue}

    def _execute_tool(self, name: str) -> object:
        handlers = {
            "get_current_time": self.get_current_time,
            "get_system_timezone": self.get_system_timezone,
            "get_revenue_summary": self.get_revenue_summary,
            "get_dominant_subreddit": self.get_dominant_subreddit,
        }
        handler = handlers.get(name)
        if handler is None:
            return {"error": f"unknown_tool:{name}"}
        return handler()

    def chat(self, messages: list[dict], task_type: str = "chat", model: str | None = None) -> str:
        model_name = str(model or self._model_policy_engine.get_model(task_type))
        response = self._client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=self._tool_spec(),
        )
        message = response.choices[0].message

        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            return str(getattr(message, "content", "") or "")

        serialized_tool_calls = [
            {
                "id": getattr(tool_call, "id", ""),
                "type": "function",
                "function": {
                    "name": getattr(getattr(tool_call, "function", None), "name", ""),
                    "arguments": getattr(getattr(tool_call, "function", None), "arguments", "{}"),
                },
            }
            for tool_call in tool_calls
        ]
        extended_messages = [
            *messages,
            {"role": "assistant", "content": getattr(message, "content", "") or "", "tool_calls": serialized_tool_calls},
        ]
        for tool_call in tool_calls:
            function_payload = getattr(tool_call, "function", None)
            function_name = getattr(function_payload, "name", "")
            tool_result = self._execute_tool(str(function_name))
            extended_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": getattr(tool_call, "id", ""),
                    "content": json.dumps(tool_result) if isinstance(tool_result, (dict, list)) else str(tool_result),
                }
            )

        followup = self._client.chat.completions.create(
            model=model_name,
            messages=extended_messages,
            tools=self._tool_spec(),
        )
        return str(getattr(followup.choices[0].message, "content", "") or "")
