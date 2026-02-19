from typing import Any

from core.errors import (
    CLIENT_ERROR,
    CONFLICT,
    DEPENDENCY_ERROR,
    INVARIANT_VIOLATION,
    NOT_FOUND,
    SERVER_ERROR,
)

ERROR_TYPES = {
    CLIENT_ERROR,
    SERVER_ERROR,
    DEPENDENCY_ERROR,
    INVARIANT_VIOLATION,
    NOT_FOUND,
    CONFLICT,
}


def success(data: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
    }


def error(error_type: str, code: str, message: str) -> dict[str, Any]:
    normalized_error_type = error_type if error_type in ERROR_TYPES else SERVER_ERROR
    return {
        "ok": False,
        "error": {
            "type": normalized_error_type,
            "code": code,
            "message": message,
        },
    }
