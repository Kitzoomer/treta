from typing import Any

from core.errors import ErrorType

ERROR_TYPES = {
    ErrorType.CLIENT_ERROR,
    ErrorType.SERVER_ERROR,
    ErrorType.DEPENDENCY_ERROR,
    ErrorType.INVARIANT_VIOLATION,
    ErrorType.NOT_FOUND,
    ErrorType.CONFLICT,
}


def success(data: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
    }


def error(error_type: str, code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_error_type = error_type if error_type in ERROR_TYPES else ErrorType.SERVER_ERROR
    return {
        "ok": False,
        "error": {
            "type": normalized_error_type,
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
