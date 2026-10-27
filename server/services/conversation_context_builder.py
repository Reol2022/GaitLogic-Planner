"""Privacy-scoped, budgeted history selection for Coach conversations.

Conversation history is linguistic context only.  Authoritative training facts
continue to be read through the existing user-scoped Coach tools.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from planner_core.database.models import CoachMessage
from server.agent.schemas import AgentConversationMessage


_ASCII_WORD = re.compile(r"[A-Za-z0-9_]+")
_CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))


class ApproximateTokenEstimator:
    """Conservative tokenizer-independent estimate.

    It deliberately does not claim equivalence with a provider tokenizer. CJK
    characters and punctuation are charged more realistically than the former
    fixed ``characters / 3`` approximation.
    """

    @staticmethod
    def estimate(content: str) -> int:
        cjk = 0
        ascii_word_chars = 0
        for match in _ASCII_WORD.finditer(content):
            ascii_word_chars += len(match.group(0))
        for char in content:
            codepoint = ord(char)
            if any(start <= codepoint <= end for start, end in _CJK_RANGES):
                cjk += 1
        non_whitespace = sum(1 for char in content if not char.isspace())
        punctuation_or_symbols = max(0, non_whitespace - cjk - ascii_word_chars)
        return max(1, cjk + math.ceil(ascii_word_chars / 4) + punctuation_or_symbols)


@dataclass(frozen=True)
class ConversationContextWindow:
    messages: list[AgentConversationMessage]
    omitted_messages: list[CoachMessage]
    trimmed: bool
    estimated_tokens: int
    summary_content: str | None
    summary_estimated_tokens: int

    @property
    def total_estimated_tokens(self) -> int:
        return self.estimated_tokens + self.summary_estimated_tokens


class ConversationContextBuilder:
    def __init__(
        self,
        *,
        max_messages: int = 24,
        token_budget: int = 4000,
        summary_token_budget: int = 1200,
    ) -> None:
        self.max_messages = max_messages
        self.token_budget = token_budget
        self.summary_token_budget = summary_token_budget

    @staticmethod
    def _tokens(content: str) -> int:
        return ApproximateTokenEstimator.estimate(content)

    def build(
        self,
        messages: Iterable[CoachMessage],
        *,
        summary_content: str | None = None,
    ) -> ConversationContextWindow:
        completed = [
            item
            for item in messages
            if item.status == "completed" and item.role in {"user", "assistant"} and item.content
        ]
        candidates = completed[-self.max_messages :]
        selected: list[CoachMessage] = []
        used = 0
        for item in reversed(candidates):
            token_count = self._tokens(item.content or "")
            if selected and used + token_count > self.token_budget:
                break
            if token_count > self.token_budget:
                continue
            selected.append(item)
            used += token_count
        selected.reverse()
        selected_ids = {item.id for item in selected}
        omitted = [item for item in completed if item.id not in selected_ids]
        safe_summary = self._bounded_summary(summary_content)
        return ConversationContextWindow(
            messages=[
                AgentConversationMessage(role=item.role, content=item.content or "")
                for item in selected
            ],
            omitted_messages=omitted,
            trimmed=len(selected) < len(completed),
            estimated_tokens=used,
            summary_content=safe_summary,
            summary_estimated_tokens=self._tokens(safe_summary) if safe_summary else 0,
        )

    def _bounded_summary(self, value: str | None) -> str | None:
        if not value:
            return None
        if self._tokens(value) <= self.summary_token_budget:
            return value
        # Summaries are persisted below their own budget. This defensive path
        # keeps a malformed legacy row from displacing recent conversation.
        # The estimator gives CJK characters a larger weight, so a fixed
        # character slice is not sufficient to guarantee the stated budget.
        bounded = value
        while self._tokens(bounded) > self.summary_token_budget and len(bounded) > 1:
            estimate = self._tokens(bounded)
            next_length = max(1, int(len(bounded) * self.summary_token_budget / estimate))
            if next_length >= len(bounded):
                next_length = len(bounded) - 1
            bounded = bounded[:next_length]
        return bounded or None
