from __future__ import annotations

from datetime import datetime, timezone
import importlib

from core.config import OPENCLAW_BASE_URL, OPENCLAW_TIMEOUT_SECONDS


def _load_requests_module():
    return importlib.import_module("requests")


class OpenClawExecutor:
    name = "openclaw_executor"
    supported_types = [
        "queue_openclaw_task",
        "external_publish",
        "external_price_update",
    ]

    def execute(self, action: dict, context: dict) -> dict:
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "task_type": str(action.get("type") or ""),
            "action_id": str(action.get("id") or ""),
            "correlation_id": action.get("correlation_id") or context.get("correlation_id"),
            "metadata": action.get("metadata", {}),
            "requested_at": now_iso,
        }

        try:
            requests = _load_requests_module()
            response = requests.post(
                f"{OPENCLAW_BASE_URL.rstrip('/')}/tasks",
                json=payload,
                timeout=OPENCLAW_TIMEOUT_SECONDS,
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
