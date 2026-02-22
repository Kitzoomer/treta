from __future__ import annotations

import contextvars
import json
import logging
import os
from datetime import datetime, timezone


_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def set_request_id(request_id: str) -> None:
    _request_id_ctx.set(str(request_id or ""))


def clear_request_id() -> None:
    _request_id_ctx.set("")


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "") or _request_id_ctx.get(),
        }
        event_type = getattr(record, "event_type", None)
        if event_type:
            payload["event_type"] = event_type

        skip_keys = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
        }
        for key, value in record.__dict__.items():
            if key not in skip_keys and key not in payload:
                payload[key] = value

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    level_name = os.getenv("TRETA_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

