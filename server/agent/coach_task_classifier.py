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
    _CAPABILITY_MARKERS = ("可以读取", "能读取", "能看", "可以看", "can you read", "can you access")
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
        has_data_scope = any(marker in normalized for marker in ("训练数据", "我的数据", "training data", "my data"))
        has_capability = any(marker in normalized for marker in cls._CAPABILITY_MARKERS)
        has_analysis_action = any(marker in normalized for marker in cls._ANALYSIS_ACTIONS)
        return has_data_scope and has_capability and not has_analysis_action

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
