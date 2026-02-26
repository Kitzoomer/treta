from __future__ import annotations

import logging

try:
    import tiktoken
except Exception:  # pragma: no cover - optional dependency
    tiktoken = None


logger = logging.getLogger(__name__)


class ContextController:
    def __init__(self) -> None:
        self._encoder = (
            tiktoken.get_encoding("cl100k_base") if tiktoken is not None else None
        )

    def build_messages(
        self,
        system_prompt: str,
        user_message: str,
        memory_messages: list[dict],
        max_messages: int = 10,
        strategic_snapshot: str = "",
        max_input_tokens: int = 6000,
        reserve_output_tokens: int = 800,
    ) -> list[dict]:
        history_limit = max(int(max_messages), 0)
        normalized_history = [
            dict(message) for message in memory_messages if isinstance(message, dict)
        ]
        recent_history = normalized_history[-history_limit:] if history_limit else []

        messages: list[dict] = [{"role": "system", "content": str(system_prompt)}]
        snapshot_text = str(strategic_snapshot or "").strip()
        if snapshot_text:
            messages.append(
                {"role": "system", "content": f"Strategic Snapshot: {snapshot_text}"}
            )
        for item in recent_history:
            role = str(item.get("role", "")).strip()
            content = item.get("content", item.get("text", ""))
            if not role:
                continue
            messages.append({"role": role, "content": str(content)})

        messages.append({"role": "user", "content": str(user_message)})
        budget_tokens = max(int(max_input_tokens) - int(reserve_output_tokens), 1)
        tokens_before = self.count_tokens(messages)
        if tokens_before > budget_tokens:
            messages = self.truncate_messages_to_budget(
                messages=messages, budget_tokens=budget_tokens
            )
            logger.info(
                "context_messages_truncated",
                extra={
                    "tokens_before": tokens_before,
                    "tokens_after": self.count_tokens(messages),
                    "budget": budget_tokens,
                },
            )
        return messages

    def count_tokens(self, messages: list[dict]) -> int:
        total = 0
        for message in messages:
            text = f"{message.get('role', '')}: {message.get('content', '')}"
            if self._encoder is not None:
                total += len(self._encoder.encode(text)) + 4
            else:
                total += max(len(str(text)) // 4, 1)
        return max(total, 1)

    def truncate_messages_to_budget(
        self, messages: list[dict], budget_tokens: int
    ) -> list[dict]:
        if not messages:
            return []
        budget_tokens = max(int(budget_tokens), 1)
        if self.count_tokens(messages) <= budget_tokens:
            return [dict(item) for item in messages]

        result: list[dict] = [dict(messages[0])]
        current_user = dict(messages[-1])

        snapshot_index = None
        for idx, item in enumerate(messages[1:-1], start=1):
            if str(item.get("role", "")).strip() == "system" and str(
                item.get("content", "")
            ).startswith("Strategic Snapshot:"):
                snapshot_index = idx
                break

        history_candidates: list[dict] = []
        for idx, item in enumerate(messages[1:-1], start=1):
            if idx == snapshot_index:
                continue
            history_candidates.append(dict(item))

        if snapshot_index is not None:
            snapshot_message = dict(messages[snapshot_index])
            with_snapshot = [*result, snapshot_message, current_user]
            if self.count_tokens(with_snapshot) <= budget_tokens:
                result.append(snapshot_message)
            else:
                truncated_snapshot = self._truncate_message_content_to_fit(
                    message=snapshot_message,
                    base_messages=[*result, current_user],
                    budget_tokens=budget_tokens,
                )
                if truncated_snapshot is not None:
                    result.append(truncated_snapshot)

        kept_history: list[dict] = []
        for item in reversed(history_candidates):
            candidate = [*result, item, *kept_history, current_user]
            if self.count_tokens(candidate) <= budget_tokens:
                kept_history.insert(0, item)
        candidate_messages = [*result, *kept_history, current_user]

        if self.count_tokens(candidate_messages) > budget_tokens:
            truncated_user = self._truncate_message_content_to_fit(
                message=current_user,
                base_messages=[*result, *kept_history],
                budget_tokens=budget_tokens,
            )
            if truncated_user is not None:
                current_user = truncated_user

        final_messages = [*result, *kept_history, current_user]
        return final_messages

    def _truncate_message_content_to_fit(
        self,
        message: dict,
        base_messages: list[dict],
        budget_tokens: int,
    ) -> dict | None:
        content = str(message.get("content", ""))
        if not content:
            candidate = {**message, "content": ""}
            return (
                candidate
                if self.count_tokens([*base_messages, candidate]) <= budget_tokens
                else None
            )

        low, high = 0, len(content)
        best: dict | None = None
        while low <= high:
            mid = (low + high) // 2
            suffix = "…" if mid < len(content) and mid > 0 else ""
            candidate = {**message, "content": f"{content[:mid].rstrip()}{suffix}"}
            if self.count_tokens([*base_messages, candidate]) <= budget_tokens:
                best = candidate
                low = mid + 1
            else:
                high = mid - 1
        return best
