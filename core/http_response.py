from typing import Any


def ok(data: Any, request_id: str) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "error": None,
        "request_id": request_id,
    }


def error(code: str, message: str, details: dict[str, Any] | None, request_id: str) -> dict[str, Any]:
    normalized_details = details or {}
    error_type = normalized_details.get("type", "server_error")
    return {
        "ok": False,
        "data": None,
        "error": {
            "type": error_type,
            "code": code,
            "message": message,
            "details": normalized_details,
        },
        "request_id": request_id,
    }
