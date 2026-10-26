from __future__ import annotations

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentConversationMessage


class CoachTaskClassifier:
    """Select a bounded execution profile for the existing Coach Agent.

    It never makes a training decision and never treats chat history as facts.
    History is used solely to recognise a follow-up question.
    """

    _TODAY_MARKERS = ("today", "今天", "今日", "今天跑", "该不该跑")
    _STATE_MARKERS = ("runner state", "training state", "跑者状态", "训练状态")
    _GREETING_MARKERS = ("你好", "您好", "嗨", "哈喽", "hello", "hi", "hey", "谢谢", "再见")
    _PERSONAL_MARKERS = (
        "我的训练", "我最近", "我的跑量", "我的计划", "读取我的", "训练数据",
        "帮我", "帮我优化", "帮我调整", "我该如何", "我应该如何", "半马", "马拉松",
        "比赛", "恢复", "疲劳", "睡眠", "心率", "配速", "race", "my training",
        "my plan", "my mileage", "my recovery",
    )
    _CAPABILITY_MARKERS = (
        "\u53ef\u4ee5\u8bfb\u53d6", "\u80fd\u8bfb\u53d6", "\u80fd\u770b", "\u53ef\u4ee5\u770b",
        "can you read", "can you access",
    )
    _PERSONAL_READ_MARKERS = (
        "\u8bfb\u53d6\u6211", "\u8bfb\u4e00\u4e0b\u6211", "\u67e5\u770b\u6211", "\u770b\u770b\u6211",
        "\u6211\u7684\u8fd1\u671f\u8bad\u7ec3", "\u6211\u8fd1\u671f\u7684\u8bad\u7ec3",
        "\u6700\u8fd1\u56db\u5468", "\u8fd1\u56db\u5468", "\u8fd1\u671f\u8bad\u7ec3", "\u8fd1\u671f\u7684\u8bad\u7ec3", "\u8bad\u7ec3\u8bb0\u5f55",
    )
    _PERSONAL_TRAINING_TIME_SCOPES = (
        "\u672c\u6708\u8bad\u7ec3", "\u8fd9\u4e2a\u6708\u8bad\u7ec3", "\u4e0a\u4e2a\u6708\u8bad\u7ec3",
        "\u8fd1\u4e00\u4e2a\u6708\u8bad\u7ec3", "\u8fd130\u5929\u8bad\u7ec3", "\u8fd1\u4e09\u5341\u5929\u8bad\u7ec3",
        "this month's training", "this month training", "last month's training", "last 30 days training",
    )
    _PERSONAL_FACT_ACTIONS = (
        "\u8bfb\u53d6", "\u67e5\u770b", "\u770b\u770b", "\u5206\u6790", "\u8bc4\u4f30", "\u6c47\u603b", "\u7edf\u8ba1",
        "read", "show", "analyze", "analyse", "review",
    )
    _FACT_QUERY_MARKERS = ("明天跑什么", "明日跑什么", "明天的计划", "明日的计划", "tomorrow's workout", "tomorrow workout")
    _STATUS_MARKERS = ("最近训练状态", "近期训练状态", "最近状态怎么样", "训练状态怎么样", "recent training status")
    _ANALYSIS_ACTIONS = ("优化", "调整", "分析", "评估", "建议", "安排", "optimize", "adjust", "analyse", "analyze")
    _PLAN_SCOPE_MARKERS = ("计划", "课表", "周期", "比赛", "半马", "马拉松", "下周", "未来", "plan", "schedule", "race")
    _FOLLOW_UP_MARKERS = ("那", "这个", "它", "继续", "基于上面", "上一条", "then", "what about")

    @classmethod
    def classify(
        cls,
        message: str,
        conversation_context: list[AgentConversationMessage] | None = None,
    ) -> AgentIntent:
        normalized = message.strip().lower()
        if any(marker in normalized for marker in cls._TODAY_MARKERS):
            return AgentIntent.TODAY_RECOMMENDATION
        if any(marker in normalized for marker in cls._STATUS_MARKERS):
            return AgentIntent.PERSONAL_TRAINING_STATUS
        if any(marker in normalized for marker in cls._STATE_MARKERS):
            return AgentIntent.EXPLAIN_RUNNER_STATE
        if normalized.rstrip("!！。.?？") in cls._GREETING_MARKERS:
            return AgentIntent.CASUAL_CONVERSATION
        if cls._is_capability_query(normalized):
            return AgentIntent.COACH_CAPABILITY_QUERY
        if cls._is_personal_read_request(normalized):
            return AgentIntent.PERSONAL_TRAINING_ANALYSIS
        if any(marker in normalized for marker in cls._FACT_QUERY_MARKERS):
            return AgentIntent.PERSONAL_TRAINING_FACT_QUERY
        if cls._is_plan_adjustment_analysis(normalized):
            return AgentIntent.PLAN_ADJUSTMENT_ANALYSIS
        if any(marker in normalized for marker in cls._PERSONAL_MARKERS):
            return AgentIntent.PERSONAL_TRAINING_ANALYSIS
        if cls._is_personal_follow_up(normalized, conversation_context or []):
            return AgentIntent.PERSONAL_TRAINING_ANALYSIS
        return AgentIntent.GENERAL_TRAINING_QUESTION

    @classmethod
    def _is_capability_query(cls, normalized: str) -> bool:
        has_data_scope = any(
            marker in normalized
            for marker in (
                "\u8bad\u7ec3\u6570\u636e", "\u6211\u7684\u6570\u636e", "\u8fd1\u671f\u8bad\u7ec3", "\u8fd1\u671f\u7684\u8bad\u7ec3",
                "\u8bad\u7ec3\u8bb0\u5f55", "training data", "my data",
            )
        )
        has_capability = any(marker in normalized for marker in cls._CAPABILITY_MARKERS)
        has_analysis_action = any(marker in normalized for marker in cls._ANALYSIS_ACTIONS)
        return has_data_scope and has_capability and not has_analysis_action

    @classmethod
    def _is_personal_read_request(cls, normalized: str) -> bool:
        if any(marker in normalized for marker in cls._PERSONAL_READ_MARKERS):
            return True
        return (
            any(marker in normalized for marker in cls._PERSONAL_TRAINING_TIME_SCOPES)
            and any(action in normalized for action in cls._PERSONAL_FACT_ACTIONS)
        )

    @classmethod
    def _is_plan_adjustment_analysis(cls, normalized: str) -> bool:
        """Recognise an adjustment analysis, not an instruction to mutate a plan."""

        return (
            any(marker in normalized for marker in cls._ANALYSIS_ACTIONS)
            and any(marker in normalized for marker in cls._PLAN_SCOPE_MARKERS)
            and any(marker in normalized for marker in cls._PERSONAL_MARKERS)
        )

    @classmethod
    def _is_personal_follow_up(
        cls,
        normalized: str,
        conversation_context: list[AgentConversationMessage],
    ) -> bool:
        if not normalized.startswith(cls._FOLLOW_UP_MARKERS):
            return False
        recent_user_messages = [
            item.content.lower() for item in conversation_context[-6:] if item.role == "user"
        ]
        return any(
            any(marker in previous for marker in cls._PERSONAL_MARKERS)
            for previous in recent_user_messages
        )
