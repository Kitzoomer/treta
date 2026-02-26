from __future__ import annotations

from datetime import datetime, timezone
import importlib
import os

OPENCLAW_BASE_URL = None
OPENCLAW_TIMEOUT_SECONDS = 5


class OpenClawExecutor:
    name = "openclaw_executor"
    supported_types = [
        "queue_openclaw_task",
        "external_publish",
        "external_price_update",
    ]

    def execute(self, action: dict, context: dict) -> dict:
        base_url = OPENCLAW_BASE_URL or os.getenv("OPENCLAW_BASE_URL", "")
        timeout_seconds = OPENCLAW_TIMEOUT_SECONDS
        timeout_from_env = os.getenv("OPENCLAW_TIMEOUT_SECONDS")

        if timeout_from_env is not None:
            try:
                timeout_seconds = int(timeout_from_env)
            except ValueError:
                timeout_seconds = OPENCLAW_TIMEOUT_SECONDS

        now_iso = datetime.now(timezone.utc).isoformat()

        payload = {
            "task_type": str(action.get("type") or ""),
            "action_id": str(action.get("id") or ""),
            "correlation_id": action.get("correlation_id") or context.get("correlation_id"),
            "metadata": action.get("metadata", {}),
            "requested_at": now_iso,
        }

        try:
            try:
                import requests
            except Exception:
                requests = importlib.import_module("requests")

            response = requests.post(
                f"{str(base_url).rstrip('/')}/tasks",
                json=payload,
                timeout=timeout_seconds,
            )

            if 200 <= response.status_code < 300:
                data = response.json() if response.content else {}
                return {
                    "status": "queued",
                    "openclaw_task_id": data.get("task_id"),
                }

            return {
                "status": "failed",
                "error": response.text,
            }

        except Exception as exc:
            return {
                "status": "failed",
                "error": str(exc),
            }
