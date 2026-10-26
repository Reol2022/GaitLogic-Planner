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
        "帮我优化", "帮我调整", "我该如何", "我应该如何", "半马", "马拉松",
        "比赛", "恢复", "疲劳", "睡眠", "心率", "配速", "race", "my training",
        "my plan", "my mileage", "my recovery",
    )
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
        if any(marker in normalized for marker in cls._STATE_MARKERS):
            return AgentIntent.EXPLAIN_RUNNER_STATE
        if normalized.rstrip("!！。.?？") in cls._GREETING_MARKERS:
            return AgentIntent.CASUAL_CONVERSATION
        if any(marker in normalized for marker in cls._PERSONAL_MARKERS):
            return AgentIntent.PERSONAL_TRAINING_ANALYSIS
        if cls._is_personal_follow_up(normalized, conversation_context or []):
            return AgentIntent.PERSONAL_TRAINING_ANALYSIS
        return AgentIntent.GENERAL_TRAINING_QUESTION

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
