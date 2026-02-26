from __future__ import annotations

from types import SimpleNamespace

from core.context_controller import ContextController
from core.gpt_client import GPTClient
from core.model_policy_engine import ModelPolicyEngine


class _FakeOpenAIClient:
    def __init__(self):
        self.models_used: list[str] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, tools):
        self.models_used.append(model)
        message = SimpleNamespace(content="ok", tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_model_policy_engine_routes_models_by_task_type():
    policy_engine = ModelPolicyEngine()

    assert policy_engine.get_model("planning") == "gpt-4o"
    assert policy_engine.get_model("execution") == "gpt-4o-mini"
    assert policy_engine.get_model("evaluation") == "gpt-4o-mini"
    assert policy_engine.get_model("chat") == "gpt-4o-mini"
    assert policy_engine.get_model("unknown") == "gpt-4o-mini"


def test_context_controller_builds_messages_with_history_limit():
    context_controller = ContextController()

    messages = context_controller.build_messages(
        system_prompt="system",
        user_message="latest",
        memory_messages=[
            {"role": "user", "text": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "text": "u2"},
        ],
        max_messages=2,
    )

    assert messages == [
        {"role": "system", "content": "system"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "user", "content": "latest"},
    ]


def test_gpt_client_uses_model_policy_engine_for_task_type():
    openai_client = _FakeOpenAIClient()
    client = GPTClient(openai_client=openai_client)

    client.chat(messages=[{"role": "user", "content": "plan"}], task_type="planning")

    assert openai_client.models_used == ["gpt-4o"]
