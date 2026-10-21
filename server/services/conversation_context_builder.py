"""Privacy-scoped history selection for persisted Coach conversations.

Conversation history is only linguistic context. The Coach must still query the
authoritative training tools for any factual or decision-making claim.
"""
from __future__ import annotations

from dataclasses import dataclass

from planner_core.database.models import CoachMessage
from server.agent.schemas import AgentConversationMessage


@dataclass(frozen=True)
class ConversationContextWindow:
    messages: list[AgentConversationMessage]
    trimmed: bool
    estimated_tokens: int


class ConversationContextBuilder:
    def __init__(self, *, max_messages: int = 16, token_budget: int = 1800) -> None:
        self.max_messages = max_messages
        self.token_budget = token_budget

    @staticmethod
    def _tokens(content: str) -> int:
        # Conservative cross-language approximation. The existing Agent context
        # limits remain the final hard boundary before a provider call.
        return max(1, (len(content) + 2) // 3)

    def build(self, messages: list[CoachMessage]) -> ConversationContextWindow:
        completed = [
            item for item in messages
            if item.status == "completed" and item.role in {"user", "assistant"} and item.content
        ]
        candidates = completed[-self.max_messages :]
        selected: list[AgentConversationMessage] = []
        used = 0
        for item in reversed(candidates):
            token_count = self._tokens(item.content or "")
            if selected and used + token_count > self.token_budget:
                break
            if token_count > self.token_budget:
                continue
            selected.append(AgentConversationMessage(role=item.role, content=item.content or ""))
            used += token_count
        selected.reverse()
        return ConversationContextWindow(
            messages=selected,
            trimmed=len(selected) < len(completed),
            estimated_tokens=used,
        )
