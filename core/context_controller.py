from __future__ import annotations


class ContextController:
    def build_messages(
        self,
        system_prompt: str,
        user_message: str,
        memory_messages: list[dict],
        max_messages: int = 10,
    ) -> list[dict]:
        history_limit = max(int(max_messages), 0)
        normalized_history = [dict(message) for message in memory_messages if isinstance(message, dict)]
        recent_history = normalized_history[-history_limit:] if history_limit else []

        messages: list[dict] = [{"role": "system", "content": str(system_prompt)}]
        for item in recent_history:
            role = str(item.get("role", "")).strip()
            content = item.get("content", item.get("text", ""))
            if not role:
                continue
            messages.append({"role": role, "content": str(content)})

        messages.append({"role": "user", "content": str(user_message)})
        # TODO: implement real token counting and truncation strategy.
        return messages
