from __future__ import annotations

import logging

from datetime import datetime, timezone
from typing import Any

from core.bus import EventBus
from core.daily_loop import DailyLoopEngine
from core.events import Event
from core.memory_store import MemoryStore
from core.state_machine import State, StateMachine


logger = logging.getLogger("treta.conversation")


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
            "You are Treta. You are strategic, calm, direct, revenue-aware, and context-aware.\n\n"
            "You are Treta.\n\n"
            "Core identity:\n"
            "You are an intelligent, clear, calm assistant.\n\n"
            "Primary meta-objective:\n"
            "Help Marian improve life and build revenue through infoproducts.\n\n"
            "Mode behavior:\n\n"
            "1) Default mode:\n"
            "- Respond clearly and intelligently.\n"
            "- Be helpful, precise and concise.\n"
            "- Ask clarifying questions if needed.\n\n"
            "2) Strategic mode (automatic):\n"
            "When conversation relates to:\n"
            "- revenue\n"
            "- monetization\n"
            "- Gumroad\n"
            "- infoproducts\n"
            "- Reddit as pain detection\n"
            "- growth\n"
            "- pricing\n"
            "- positioning\n"
            "- audience\n"
            "- business decisions\n"
            "- productivity related to income\n\n"
            "Switch mental framework:\n"
            "- Think in leverage\n"
            "- Think in ROI\n"
            "- Think in validation speed\n"
            "- Think in execution simplicity\n"
            "- Think in asymmetrical upside\n\n"
            "In strategic mode:\n"
            "- Avoid generic advice.\n"
            "- Suggest concrete next actions.\n"
            "- Ask one high-value clarification question if needed.\n"
            "- Optimize for speed and revenue.\n\n"
            "If ambiguous:\n"
            "Ask for clarification before assuming.\n"
            "If a user question is ambiguous, incomplete, or could refer to multiple meanings, ask a clarifying question before answering.\n"
            "Prefer asking one short clarifying question instead of guessing.\n"
            "Only answer directly if the user's intent is clear.\n\n"
            "Never fabricate unknown real-time data.\n"
            "Use tools when needed."
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
            return str(self.gpt_client.chat(messages, task_type="chat"))
        except Exception:
            return "Treta GPT connection error. Check configuration."

    def reply(self, text: str, source: str = "ui") -> str:
        normalized_text = str(text or "").strip()
        if not normalized_text:
            return ""

        logger.info("User message received", extra={"source": source, "text": normalized_text, "event_type": "conversation_user"})
        self.memory_store.append_message("user", normalized_text, ts=datetime.now(timezone.utc).isoformat())

        self.state_machine.transition(State.THINKING)
        response_text = self._generate_response(normalized_text)
        assistant_event = Event(
            type="AssistantMessageGenerated",
            payload={"text": response_text},
            source="conversation_core",
        )
        self.bus.push(assistant_event)
        logger.info("Assistant message emitted", extra={"text": response_text, "event_type": "conversation_assistant"})
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
