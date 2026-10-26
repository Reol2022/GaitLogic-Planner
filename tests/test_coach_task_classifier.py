from server.agent.coach_task_classifier import CoachTaskClassifier
from server.agent.enums import AgentIntent
from server.agent.schemas import AgentConversationMessage


def test_greeting_is_casual_and_does_not_select_retrieval_profile() -> None:
    assert CoachTaskClassifier.classify("你好。") == AgentIntent.CASUAL_CONVERSATION


def test_personal_data_request_selects_read_only_personal_analysis() -> None:
    assert (
        CoachTaskClassifier.classify("你可以读取我的训练数据并帮我优化接下来的训练吗？")
        == AgentIntent.PERSONAL_TRAINING_ANALYSIS
    )


def test_capability_question_does_not_select_personal_fact_loading() -> None:
    assert (
        CoachTaskClassifier.classify("你可以读取我的训练数据吗？")
        == AgentIntent.COACH_CAPABILITY_QUERY
    )


def test_tomorrow_workout_is_a_bounded_fact_query() -> None:
    assert (
        CoachTaskClassifier.classify("我明天跑什么？")
        == AgentIntent.PERSONAL_TRAINING_FACT_QUERY
    )


def test_recent_status_uses_bounded_status_profile() -> None:
    assert (
        CoachTaskClassifier.classify("我最近训练状态怎么样？")
        == AgentIntent.PERSONAL_TRAINING_STATUS
    )


def test_half_marathon_question_selects_personal_analysis() -> None:
    assert (
        CoachTaskClassifier.classify("还有两周半马比赛，我该如何调整训练？")
        == AgentIntent.PLAN_ADJUSTMENT_ANALYSIS
    )


def test_follow_up_uses_history_only_for_routing_not_as_a_fact_source() -> None:
    history = [
        AgentConversationMessage(role="user", content="我最近训练疲劳，想看看我的训练数据"),
        AgentConversationMessage(role="assistant", content="我会读取当前可用训练事实。"),
    ]
    assert CoachTaskClassifier.classify("那应该怎么调整？", history) == AgentIntent.PERSONAL_TRAINING_ANALYSIS
