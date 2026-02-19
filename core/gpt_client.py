from __future__ import annotations

import os
from dataclasses import dataclass

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
    def __init__(self):
        if OpenAI is None:
            raise GPTClientConfigurationError("openai package not installed")

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise GPTClientConfigurationError(message="OPENAI_API_KEY is not set")
        self._client = OpenAI(api_key=api_key)

    def chat(self, messages: list[dict]) -> str:
        response = self._client.responses.create(model="gpt-4o-mini", input=messages)
        return response.output_text
