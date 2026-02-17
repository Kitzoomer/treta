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

    def _build_stub_response(self, text: str) -> str:
        snapshot = self.memory_store.snapshot()
        profile = snapshot.get("profile", {})
        name = str(profile.get("name", "Marian"))
        objective = str(profile.get("objective", "advance the daily loop"))

        phase = "IDLE"
        if self.daily_loop_engine is not None:
            phase = str(self.daily_loop_engine.compute_phase())

        user_text = text.strip()
        return (
            f"{name}, I got your message: '{user_text}'. "
            f"Current loop phase is {phase}. Objective: {objective}. "
            "Suggested next steps: 1) run an opportunity scan, 2) review top proposal, "
            "3) execute one concrete launch task today."
        )

    def _generate_response(self, text: str) -> str:
        if self.gpt_client is not None and hasattr(self.gpt_client, "generate"):
            return str(self.gpt_client.generate(text))
        return self._build_stub_response(text)

    def consume(self, event: Event) -> None:
        if event.type != "UserMessageSubmitted":
            return

        text = str(event.payload.get("text", "")).strip()
        if not text:
            return

        source = str(event.payload.get("source", event.source or "ui"))
        print(f"[CONVERSATION] user_message_received source={source} text={text}")
        self.memory_store.append_message("user", text, ts=datetime.now(timezone.utc).isoformat())

        self.state_machine.transition(State.THINKING)
        response_text = self._generate_response(text)
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
