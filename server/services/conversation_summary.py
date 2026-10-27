"""Deterministic, privacy-scoped incremental summaries for Coach Chat."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from planner_core.database.models import CoachMessage
from server.services.conversation_context_builder import ApproximateTokenEstimator


def _clean(value: str | None, *, limit: int = 280) -> str:
    return " ".join((value or "").split())[:limit]


def _append_unique(items: list[str], value: str, *, limit: int) -> list[str]:
    if not value:
        return items
    filtered = [item for item in items if item != value]
    return [*filtered, value][-limit:]


@dataclass(frozen=True)
class ConversationSummary:
    version: int = 0
    through_sequence: int = 0
    current_goal: str | None = None
    user_constraints: list[str] = field(default_factory=list)
    user_decisions: list[str] = field(default_factory=list)
    coach_proposals: list[str] = field(default_factory=list)
    unresolved_items: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, value: dict | None) -> "ConversationSummary":
        if not isinstance(value, dict):
            return cls()
        return cls(
            version=max(0, int(value.get("version") or 0)),
            through_sequence=max(0, int(value.get("through_sequence") or 0)),
            current_goal=_clean(value.get("current_goal")) or None,
            user_constraints=[_clean(item) for item in value.get("user_constraints", []) if _clean(item)],
            user_decisions=[_clean(item) for item in value.get("user_decisions", []) if _clean(item)],
            coach_proposals=[_clean(item) for item in value.get("coach_proposals", []) if _clean(item)],
            unresolved_items=[_clean(item) for item in value.get("unresolved_items", []) if _clean(item)],
        )

    def to_json(self) -> dict:
        return {
            "version": self.version,
            "through_sequence": self.through_sequence,
            "current_goal": self.current_goal,
            "user_constraints": self.user_constraints,
            "user_decisions": self.user_decisions,
            "coach_proposals": self.coach_proposals,
            "unresolved_items": self.unresolved_items,
        }

    def render(self) -> str:
        lines = [
            "Conversation summary (historical linguistic context; not authoritative training data):"
        ]
        if self.current_goal:
            lines.append(f"- User-stated current goal: {self.current_goal}")
        for item in self.user_constraints:
            lines.append(f"- User-stated preference or constraint: {item}")
        for item in self.user_decisions:
            lines.append(f"- User-confirmed or rejected discussion point: {item}")
        for item in self.coach_proposals:
            lines.append(f"- Coach proposal only; not confirmed or executed: {item}")
        for item in self.unresolved_items:
            lines.append(f"- Unresolved discussion item: {item}")
        return "\n".join(lines)


class ConversationSummarizer:
    """Compact old completed turns without an extra provider request."""

    GOAL_MARKERS = ("目标", "比赛", "马拉松", "半马", "5k", "10k", "想冲", "希望")
    CONSTRAINT_MARKERS = ("不要", "不想", "只能", "不能", "偏好", "希望", "每周", "安排")
    DECISION_MARKERS = ("同意", "确认", "就这样", "不要", "不需要", "不同意", "改成", "改为")

    def summarize(
        self,
        *,
        previous: ConversationSummary,
        messages: Iterable[CoachMessage],
        token_budget: int,
    ) -> ConversationSummary:
        goal = previous.current_goal
        constraints = list(previous.user_constraints)
        decisions = list(previous.user_decisions)
        proposals = list(previous.coach_proposals)
        unresolved = list(previous.unresolved_items)
        through = previous.through_sequence
        for message in sorted(messages, key=lambda item: item.sequence_no):
            text = _clean(message.content)
            if not text:
                continue
            through = max(through, int(message.sequence_no))
            lowered = text.lower()
            if message.role == "user":
                if any(marker in lowered for marker in self.GOAL_MARKERS) or any(
                    marker in lowered for marker in ("改成", "改为")
                ):
                    goal = text
                if any(marker in lowered for marker in self.CONSTRAINT_MARKERS):
                    constraints = _append_unique(constraints, text, limit=4)
                if any(marker in lowered for marker in self.DECISION_MARKERS):
                    decisions = _append_unique(decisions, text, limit=4)
                if "?" in text or "？" in text or not any(marker in lowered for marker in self.DECISION_MARKERS):
                    unresolved = _append_unique(unresolved, text, limit=3)
            elif message.role == "assistant":
                proposals = _append_unique(proposals, text, limit=3)
        result = ConversationSummary(
            version=previous.version + 1,
            through_sequence=through,
            current_goal=goal,
            user_constraints=constraints,
            user_decisions=decisions,
            coach_proposals=proposals,
            unresolved_items=unresolved,
        )
        return self._fit(result, token_budget)

    @staticmethod
    def _fit(summary: ConversationSummary, budget: int) -> ConversationSummary:
        value = summary
        while ApproximateTokenEstimator.estimate(value.render()) > budget:
            # A proposal must remain explicitly labelled as unconfirmed where
            # possible. It is safer to drop lower-priority open questions
            # before losing that distinction.
            if len(value.unresolved_items) > 1:
                value = ConversationSummary(**{**value.__dict__, "unresolved_items": value.unresolved_items[1:]})
            elif len(value.user_constraints) > 1:
                value = ConversationSummary(**{**value.__dict__, "user_constraints": value.user_constraints[1:]})
            elif len(value.user_decisions) > 1:
                value = ConversationSummary(**{**value.__dict__, "user_decisions": value.user_decisions[1:]})
            elif value.coach_proposals:
                value = ConversationSummary(**{**value.__dict__, "coach_proposals": value.coach_proposals[1:]})
            else:
                return ConversationSummary(
                    **{**value.__dict__, "current_goal": _clean(value.current_goal, limit=max(60, budget * 2)) or None}
                )
        return value
