import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.gpt_client import GPTClient
from core.revenue_attribution.store import RevenueAttributionStore


class _MockChatCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _MockOpenAIClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=_MockChatCompletions(responses))


class _TemporaryRateLimitError(Exception):
    def __init__(self, message="rate limit"):
        super().__init__(message)
        self.status_code = 429


class GPTClientTest(unittest.TestCase):
    def test_chat_returns_direct_message_when_no_tool_call(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hello", tool_calls=None))]
        )
        openai_client = _MockOpenAIClient([response])
        client = GPTClient(openai_client=openai_client)

        result = client.chat([{"role": "user", "content": "hi"}])

        self.assertEqual(result, "hello")
        self.assertEqual(len(openai_client.chat.completions.calls), 1)
        self.assertIn("tools", openai_client.chat.completions.calls[0])

    def test_chat_executes_tool_and_requests_follow_up(self):
        tool_call = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(name="get_system_timezone", arguments="{}"),
        )
        first_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[tool_call]))]
        )
        second_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="timezone sent"))]
        )
        openai_client = _MockOpenAIClient([first_response, second_response])
        client = GPTClient(openai_client=openai_client)

        previous_timezone = os.environ.get("TRETA_TIMEZONE")
        os.environ["TRETA_TIMEZONE"] = "UTC"
        try:
            result = client.chat([{"role": "user", "content": "what timezone?"}])
        finally:
            if previous_timezone is None:
                os.environ.pop("TRETA_TIMEZONE", None)
            else:
                os.environ["TRETA_TIMEZONE"] = previous_timezone

        self.assertEqual(result, "timezone sent")
        self.assertEqual(len(openai_client.chat.completions.calls), 2)
        followup_messages = openai_client.chat.completions.calls[1]["messages"]
        self.assertEqual(followup_messages[-1]["role"], "tool")
        self.assertEqual(followup_messages[-1]["tool_call_id"], "call_1")
        self.assertEqual(followup_messages[-1]["content"], "UTC")


    def test_chat_passes_optional_generation_parameters_when_provided(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hello", tool_calls=None))]
        )
        openai_client = _MockOpenAIClient([response])
        client = GPTClient(openai_client=openai_client)

        result = client.chat(
            [{"role": "user", "content": "hi"}],
            temperature=0.2,
            max_tokens=64,
            top_p=0.9,
            response_format={"type": "json_object"},
        )

        self.assertEqual(result, "hello")
        first_call = openai_client.chat.completions.calls[0]
        self.assertEqual(first_call["temperature"], 0.2)
        self.assertEqual(first_call["max_tokens"], 64)
        self.assertEqual(first_call["top_p"], 0.9)
        self.assertEqual(first_call["response_format"], {"type": "json_object"})

    def test_chat_retries_once_with_fallback_model_on_temporary_error(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok fallback", tool_calls=None))]
        )
        completions = _MockChatCompletions([_TemporaryRateLimitError(), response])

        def _create(**kwargs):
            call_response = completions._responses.pop(0)
            completions.calls.append(kwargs)
            if isinstance(call_response, Exception):
                raise call_response
            return call_response

        openai_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
        client = GPTClient(openai_client=openai_client)

        result = client.chat([{"role": "user", "content": "plan"}], task_type="planning")

        self.assertEqual(result, "ok fallback")
        self.assertEqual(len(completions.calls), 2)
        self.assertEqual(completions.calls[0]["model"], "gpt-4o")
        self.assertEqual(completions.calls[1]["model"], "gpt-4o-mini")

    def test_revenue_tools_use_existing_store(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = RevenueAttributionStore(path=Path(tmp_dir) / "revenue_attribution.json")
            store.upsert_tracking(tracking_id="t1", proposal_id="proposal-1", product_id="product-1", subreddit="python")
            store.upsert_tracking(tracking_id="t2", proposal_id="proposal-2", product_id="product-2", subreddit="saas")
            store.record_sale(tracking_id="t1", sale_count=1, revenue_delta=120.0)
            store.record_sale(tracking_id="t2", sale_count=1, revenue_delta=80.0)
            client = GPTClient(openai_client=_MockOpenAIClient([]), revenue_attribution_store=store)

            summary = client.get_revenue_summary()
            dominant = client.get_dominant_subreddit()

            self.assertEqual(summary["totals"]["sales"], 2)
            self.assertEqual(summary["totals"]["revenue"], 200.0)
            self.assertEqual(dominant["subreddit"], "python")
            self.assertEqual(dominant["revenue"], 120.0)


if __name__ == "__main__":
    unittest.main()
