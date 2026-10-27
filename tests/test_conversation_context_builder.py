from types import SimpleNamespace

import pytest

from server.services.conversation_context_builder import (
    ApproximateTokenEstimator,
    ConversationContextBuilder,
)
from server.services.conversation_summary import ConversationSummarizer, ConversationSummary


def _messages(turn_count: int):
    values = []
    for index in range(turn_count):
        values.extend(
            [
                SimpleNamespace(
                    id=index * 2 + 1,
                    role="user",
                    status="completed",
                    content=f"Synthetic runner discussion turn {index}: keep the goal evidence based.",
                    sequence_no=index * 2 + 1,
                ),
                SimpleNamespace(
                    id=index * 2 + 2,
                    role="assistant",
                    status="completed",
                    content=f"Synthetic coach reply {index}: this remains a proposal, not an executed plan.",
                    sequence_no=index * 2 + 2,
                ),
            ]
        )
    return values


@pytest.mark.parametrize("turn_count", [5, 15, 30, 50])
def test_long_conversation_keeps_recent_window_and_summary_within_separate_budgets(turn_count: int) -> None:
    builder = ConversationContextBuilder(
        max_messages=24,
        token_budget=4000,
        summary_token_budget=1200,
    )
    messages = _messages(turn_count)
    window = builder.build(messages)

    assert len(window.messages) <= 24
    assert window.estimated_tokens <= 4000
    if len(messages) <= 24:
        assert not window.omitted_messages
        return

    summary = ConversationSummarizer().summarize(
        previous=ConversationSummary(),
        messages=window.omitted_messages,
        token_budget=1200,
    )
    rebuilt = builder.build(messages, summary_content=summary.render())
    assert rebuilt.summary_content
    assert rebuilt.summary_estimated_tokens <= 1200
    assert rebuilt.estimated_tokens <= 4000
    assert rebuilt.total_estimated_tokens <= 5200


def test_malformed_persisted_summary_cannot_exceed_its_budget_or_displace_recent_messages() -> None:
    builder = ConversationContextBuilder(max_messages=24, token_budget=4000, summary_token_budget=256)
    window = builder.build(_messages(15), summary_content="训" * 4000)

    assert len(window.messages) == 24
    assert window.summary_content
    assert ApproximateTokenEstimator.estimate(window.summary_content) <= 256
