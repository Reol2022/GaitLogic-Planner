from __future__ import annotations

from pathlib import Path

from planner_core.config import Settings
from scripts.smoke_coach_rag import render_report
from server.agent.enums import AgentIntent, AgentRiskLevel
from server.agent.gateway import MockAgentLLMGateway
from server.agent.schemas import AgentModelOutput, AgentNotice, AgentTodayRecommendation
from server.agent.smoke import CoachRagSmokeRunner
from server.agent.tools.knowledge_tools import RetrieveTrainingKnowledgeTool
from server.knowledge_retrieval.enums import (
    KnowledgeCategory,
    KnowledgeEvidenceLevel,
)
from server.knowledge_retrieval.retrieval_schemas import (
    KnowledgeRetrievalResponse,
    KnowledgeRetrievalResult,
)
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever


class _SuccessfulRetriever(TrainingKnowledgeRetriever):
    def __init__(self) -> None:
        pass

    def retrieve(self, request):
        return KnowledgeRetrievalResponse(
            query=request.query,
            results=[
                KnowledgeRetrievalResult(
                    rank=1,
                    score=0.9,
                    chunk_id="fictional-document#core#001",
                    document_id="fictional-document",
                    title="虚构训练知识",
                    section="核心原则",
                    excerpt="这是一段只用于自动测试的虚构知识摘录。",
                    category=KnowledgeCategory.GENERAL,
                    tags=["fictional"],
                    source_id="fictional-source",
                    source_title="Fictional Source",
                    knowledge_version="1.0.0",
                    evidence_level=KnowledgeEvidenceLevel.INTERNAL,
                    relative_path="documents/fictional.md",
                    limitations=[],
                )
            ],
            limitations=[],
            index_id="knowledge-" + "1" * 24,
            corpus_root_hash="1" * 64,
        )


class _DeterministicSmokeRunner(CoachRagSmokeRunner):
    def _knowledge_tool(self, mode):
        if mode == "configured":
            return RetrieveTrainingKnowledgeTool(_SuccessfulRetriever)
        return super()._knowledge_tool(mode)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        COACH_AGENT_ENABLED=True,
        COACH_AGENT_API_KEY="fictional-secret",
        COACH_AGENT_BASE_URL="https://chat.example.test/v1",
        COACH_AGENT_MODEL="fictional-chat-model",
        KNOWLEDGE_EMBEDDING_ENABLED=True,
        KNOWLEDGE_EMBEDDING_API_KEY="fictional-embedding-secret",
        KNOWLEDGE_EMBEDDING_BASE_URL="https://embedding.example.test/v1",
        KNOWLEDGE_EMBEDDING_MODEL="fictional-embedding-model",
        KNOWLEDGE_EMBEDDING_DIMENSIONS=32,
        COACH_AGENT_KNOWLEDGE_RETRIEVAL_ENABLED=True,
        COACH_AGENT_KNOWLEDGE_INDEX_ID="knowledge-" + "1" * 24,
    )


def _gateway_factory():
    outputs = iter(
        [
            AgentModelOutput(
                answer="阈值训练需要渐进安排。",
                summary="渐进安排",
                intent=AgentIntent.GENERAL_TRAINING_QUESTION,
                risk_level=AgentRiskLevel.LOW,
                knowledge_reference_ids=["knowledge_1"],
            ),
            AgentModelOutput(
                answer="当前虚构状态需结合数据限制解释。",
                summary="保留数据限制",
                intent=AgentIntent.EXPLAIN_RUNNER_STATE,
                risk_level=AgentRiskLevel.UNKNOWN,
                limitations=[
                    AgentNotice(
                        code="FICTIONAL_DATA_LIMITED",
                        message="部分虚构字段缺失。",
                    )
                ],
                knowledge_reference_ids=["knowledge_1"],
            ),
            AgentModelOutput(
                answer="请按确定性建议谨慎执行。",
                summary="谨慎执行",
                intent=AgentIntent.TODAY_RECOMMENDATION,
                risk_level=AgentRiskLevel.MODERATE,
                knowledge_reference_ids=["knowledge_1"],
                today_recommendation=AgentTodayRecommendation(
                    decision="PROCEED_WITH_CAUTION",
                    planned_workout_status="PLANNED",
                    headline="建议谨慎执行今日训练。",
                    data_quality="AVAILABLE",
                ),
            ),
            AgentModelOutput(
                answer="知识检索不可用时保留确定性建议。",
                summary="安全降级",
                intent=AgentIntent.TODAY_RECOMMENDATION,
                risk_level=AgentRiskLevel.MODERATE,
                limitations=[
                    AgentNotice(
                        code="KNOWLEDGE_RETRIEVAL_UNAVAILABLE",
                        message="训练知识检索暂不可用。",
                    )
                ],
                today_recommendation=AgentTodayRecommendation(
                    decision="PROCEED_WITH_CAUTION",
                    planned_workout_status="PLANNED",
                    headline="建议谨慎执行今日训练。",
                    data_quality="AVAILABLE",
                ),
            ),
            AgentModelOutput(
                answer="当前没有可用的知识引用。",
                summary="知识覆盖有限",
                intent=AgentIntent.GENERAL_TRAINING_QUESTION,
                risk_level=AgentRiskLevel.UNKNOWN,
                limitations=[
                    AgentNotice(
                        code="KNOWLEDGE_RETRIEVAL_EMPTY",
                        message="当前知识库没有匹配内容。",
                    )
                ],
            ),
        ]
    )

    def factory(_settings):
        return MockAgentLLMGateway(next(outputs))

    return factory


def test_six_smoke_contracts_are_safe_and_deterministic() -> None:
    report = _DeterministicSmokeRunner(
        _settings(),
        gateway_factory=_gateway_factory(),
    ).run()
    assert len(report.scenarios) == 6
    assert report.passed is True
    today = next(item for item in report.scenarios if item.scenario == "TODAY")
    assert all(today.canonical_invariance.values())
    unavailable = next(
        item
        for item in report.scenarios
        if item.scenario == "KNOWLEDGE_INDEX_UNAVAILABLE"
    )
    assert unavailable.status == "DEGRADED"
    assert unavailable.knowledge_reference_count == 0
    disabled = next(
        item
        for item in report.scenarios
        if item.scenario == "PROVIDER_DISABLED"
    )
    assert disabled.status == "DEGRADED"
    assert disabled.provider_status == "DISABLED"


def test_report_omits_queries_raw_answers_context_and_credentials() -> None:
    report = _DeterministicSmokeRunner(
        _settings(),
        gateway_factory=_gateway_factory(),
    ).run()
    rendered = render_report(report)
    lowered = rendered.lower()
    assert "fictional-secret" not in rendered
    assert "这是一段只用于自动测试的虚构知识摘录" not in rendered
    assert "阈值训练通常应该怎样安排" not in rendered
    assert "prompt" in lowered  # The report explicitly states it was not saved.
    assert "context" in lowered
    assert "reasoning_content" in rendered
    assert str(Path.cwd()) not in rendered
    assert "knowledge_1" not in rendered
