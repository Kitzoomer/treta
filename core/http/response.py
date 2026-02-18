from typing import Any


def success(data: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
    }


def error(error_type: str, code: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "type": error_type,
            "code": code,
            "message": message,
        },
    }
