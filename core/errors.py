from __future__ import annotations


class ErrorType:
    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"
    DEPENDENCY_ERROR = "dependency_error"
    INVARIANT_VIOLATION = "invariant_violation"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"


class TretaError(Exception):
    """Base typed exception for Treta domain/service errors."""


class InvariantViolationError(TretaError):
    pass


class NotFoundError(TretaError):
    pass


class ConflictError(TretaError):
    pass


class DependencyError(TretaError):
    pass


# Backward-compatible module-level constants.
CLIENT_ERROR = ErrorType.CLIENT_ERROR
SERVER_ERROR = ErrorType.SERVER_ERROR
DEPENDENCY_ERROR = ErrorType.DEPENDENCY_ERROR
INVARIANT_VIOLATION = ErrorType.INVARIANT_VIOLATION
NOT_FOUND = ErrorType.NOT_FOUND
CONFLICT = ErrorType.CONFLICT
