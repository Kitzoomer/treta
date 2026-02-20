from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.bus import EventBus
from core.daily_loop import DailyLoopEngine
from core.events import Event
from core.memory_store import MemoryStore
from core.state_machine import State, StateMachine


class ConversationCore:
    def __init__(
        self,
        bus: EventBus,
        state_machine: StateMachine,
        memory_store: MemoryStore,
        gpt_client_optional: Any = None,
        daily_loop_engine: DailyLoopEngine | None = None,
    ):
        self.bus = bus
        self.state_machine = state_machine
        self.memory_store = memory_store
        self.gpt_client = gpt_client_optional
        self.daily_loop_engine = daily_loop_engine

    def _system_prompt(self) -> str:
        return (
            "You are Treta. You are strategic, calm, direct, revenue-aware, and context-aware. "
            "You help build and monetize infoproducts using Reddit pain detection and Gumroad sales. "
            "If the user asks for real-time or system-specific data, use tools instead of guessing. "
            "Do not hallucinate system data. "
            "If a user question is ambiguous, incomplete, or could refer to multiple meanings, ask a clarifying question before answering. "
            "Do not assume missing context. "
            "Prefer asking one short clarifying question instead of guessing. "
            "Only answer directly if the user's intent is clear. "
            "If a question could refer to multiple categories (such as places, products, people, or technical terms), ask which one the user means. "
            "Keep clarifying questions concise and natural."
        )

    def _generate_response(self, user_message: str) -> str:
        if self.gpt_client is None or not hasattr(self.gpt_client, "chat"):
            return "Treta GPT connection error. Check configuration."

        messages = [
            {
                "role": "system",
                "content": self._system_prompt(),
            },
            {"role": "user", "content": user_message},
        ]

        try:
            return str(self.gpt_client.chat(messages))
        except Exception:
            return "Treta GPT connection error. Check configuration."

    def reply(self, text: str, source: str = "ui") -> str:
        normalized_text = str(text or "").strip()
        if not normalized_text:
            return ""

        print(f"[CONVERSATION] user_message_received source={source} text={normalized_text}")
        self.memory_store.append_message("user", normalized_text, ts=datetime.now(timezone.utc).isoformat())

        self.state_machine.transition(State.THINKING)
        response_text = self._generate_response(normalized_text)
        assistant_event = Event(
            type="AssistantMessageGenerated",
            payload={"text": response_text},
            source="conversation_core",
        )
        self.bus.push(assistant_event)
        print(f"[CONVERSATION] assistant_message_emitted text={response_text}")
        self.memory_store.append_message("assistant", response_text, ts=assistant_event.timestamp)
        self.state_machine.transition(State.SPEAKING)
        self.state_machine.transition(State.IDLE)
        return response_text

    def consume(self, event: Event) -> None:
        if event.type != "UserMessageSubmitted":
            return

        text = str(event.payload.get("text", "")).strip()
        if not text:
            return

        source = str(event.payload.get("source", event.source or "ui"))
        self.reply(text, source=source)
