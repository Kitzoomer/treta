from __future__ import annotations

import json
from typing import Any


class OutputValidator:
    """Structural validator for JSON outputs consumed by execution engines."""

    def validate_json(self, raw_payload: str) -> dict[str, Any]:
        try:
            parsed = json.loads(str(raw_payload or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError("Output is not valid JSON") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Output must be a JSON object")
        return parsed

    def validate_schema(self, payload: dict[str, Any], schema: dict[str, Any]) -> None:
        expected_keys = set(schema.keys())
        actual_keys = set(payload.keys())
        if actual_keys != expected_keys:
            raise ValueError(f"Schema mismatch. Expected keys: {sorted(expected_keys)}")

    def validate_required_fields(self, payload: dict[str, Any], required_fields: list[str]) -> None:
        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

    def validate_non_empty_strings(self, payload: Any) -> None:
        if isinstance(payload, str):
            if payload.strip() == "":
                raise ValueError("Empty strings are not allowed")
            return

        if isinstance(payload, list):
            for item in payload:
                self.validate_non_empty_strings(item)
            return

        if isinstance(payload, dict):
            for value in payload.values():
                self.validate_non_empty_strings(value)
