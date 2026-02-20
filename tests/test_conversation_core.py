import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

from core.bus import EventBus
from core.conversation_core import ConversationCore
from core.dispatcher import Dispatcher
from core.events import Event
from core.ipc_http import start_http_server
from core.memory_store import MemoryStore
from core.state_machine import State, StateMachine




class _MockGPTClient:
    def __init__(self, response: str = "mocked gpt response"):
        self.response = response
        self.messages = None

    def chat(self, messages):
        self.messages = messages
        return self.response


class ConversationCoreTest(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    def _drain_queue(self):
        while self.bus.pop(timeout=0.001) is not None:
            pass

    def test_user_message_generates_assistant_message_and_persists_history(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            memory_store = MemoryStore(path=Path(tmp_dir) / "memory_store.json")
            dispatcher = Dispatcher(state_machine=StateMachine(), memory_store=memory_store, bus=self.bus)
            self._drain_queue()

            dispatcher.handle(
                Event(
                    type="UserMessageSubmitted",
                    source="ui",
                    payload={"text": "hello treta", "source": "ui"},
                )
            )

            generated = self.bus.pop(timeout=0.05)
            self.assertIsNotNone(generated)
            self.assertEqual(generated.type, "AssistantMessageGenerated")
            dispatcher.handle(generated)

            snapshot = memory_store.snapshot()
            history = snapshot["chat_history"]
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]["role"], "user")
            self.assertEqual(history[0]["text"], "hello treta")
            self.assertEqual(history[1]["role"], "assistant")
            self.assertTrue(history[1]["text"])
            self.assertEqual(dispatcher.sm.state, State.IDLE)


    def test_system_prompt_includes_clarification_rules(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            memory_store = MemoryStore(path=Path(tmp_dir) / "memory_store.json")
            mock_gpt = _MockGPTClient(response="from gpt")
            conversation_core = ConversationCore(
                bus=self.bus,
                state_machine=StateMachine(),
                memory_store=memory_store,
                gpt_client_optional=mock_gpt,
            )

            conversation_core.reply("What is Java?")

            self.assertIsNotNone(mock_gpt.messages)
            system_prompt = mock_gpt.messages[0]["content"]
            self.assertIn("You are Treta. You are strategic, calm, direct, revenue-aware, and context-aware.", system_prompt)
            self.assertIn("If a user question is ambiguous, incomplete, or could refer to multiple meanings, ask a clarifying question before answering.", system_prompt)
            self.assertIn("Prefer asking one short clarifying question instead of guessing.", system_prompt)
            self.assertIn("Only answer directly if the user's intent is clear.", system_prompt)

    def test_user_message_calls_gpt_client_chat(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            memory_store = MemoryStore(path=Path(tmp_dir) / "memory_store.json")
            mock_gpt = _MockGPTClient(response="from gpt")
            conversation_core = ConversationCore(
                bus=self.bus,
                state_machine=StateMachine(),
                memory_store=memory_store,
                gpt_client_optional=mock_gpt,
            )

            conversation_core.consume(
                Event(
                    type="UserMessageSubmitted",
                    source="ui",
                    payload={"text": "hello treta", "source": "ui"},
                )
            )

            generated = self.bus.pop(timeout=0.05)
            self.assertIsNotNone(generated)
            self.assertEqual(generated.type, "AssistantMessageGenerated")
            self.assertEqual(generated.payload["text"], "from gpt")
            self.assertIsNotNone(mock_gpt.messages)
            self.assertEqual(mock_gpt.messages[1]["content"], "hello treta")

    def test_memory_endpoint_returns_chat_history(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            memory_store = MemoryStore(path=Path(tmp_dir) / "memory_store.json")
            memory_store.append_message("user", "saved message")

            server = start_http_server(host="127.0.0.1", port=0, memory_store=memory_store, bus=self.bus)
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/memory", timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertIn("chat_history", payload)
                self.assertEqual(payload["chat_history"][0]["text"], "saved message")
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
