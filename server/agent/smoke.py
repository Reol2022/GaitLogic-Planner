from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Callable, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from planner_core.config import Settings
from server.agent.enums import AgentIntent, AgentRunStatus, AgentToolStatus
from server.agent.errors import AgentErrorCode
from server.agent.evaluation.fixtures import (
    EVALUATION_FIXTURES,
    EvaluationFixture,
    build_evaluation_registry,
    canonical_today_facts_for_fixture,
)
from server.agent.fallback import DeterministicCoachFallback
from server.agent.gateway import AgentLLMGateway
from server.agent.orchestrator import GaitLogicCoachAgent
from server.agent.providers.errors import AgentProviderError
from server.agent.providers.openai_compatible import OpenAICompatibleAgentGateway
from server.agent.schemas import AgentLimits, AgentRequest
from server.agent.tools.knowledge_tools import (
    RetrieveTrainingKnowledgeTool,
    build_configured_knowledge_tool,
)
from server.agent.training_context_builder import AgentTrainingContextBuilder
from server.knowledge_retrieval.retrieval_schemas import (
    KnowledgeRetrievalResponse,
)
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever


class SmokeScenarioResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: str
    intent: AgentIntent
    status: Literal["SUCCEEDED", "DEGRADED", "FAILED"]
    provider_status: Literal["SUCCEEDED", "DISABLED", "FAILED"]
    tool_names: list[str]
    knowledge_reference_count: int = Field(ge=0)
    public_document_ids: list[str]
    validation_codes: list[str]
    latency_ms: float = Field(ge=0)
    usage: dict[str, int | float | str | None]
    canonical_invariance: dict[str, bool] = Field(default_factory=dict)
    passed: bool


class CoachRagSmokeReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fictional_data: bool = True
    provider: str
    chat_model: str
    embedding_model: str
    scenarios: list[SmokeScenarioResult]
    business_row_count_before: int = Field(ge=0)
    business_row_count_after: int = Field(ge=0)
    business_write_count: int = Field(ge=0)
    residual_database_count: int = Field(ge=0)

    @property
    def passed(self) -> bool:
        return (
            all(item.passed for item in self.scenarios)
            and self.business_write_count == 0
            and self.residual_database_count == 0
        )


class _DisabledGateway(AgentLLMGateway):
    def generate(self, **_kwargs):
        raise AgentProviderError(AgentErrorCode.AGENT_PROVIDER_DISABLED)


class _UnavailableRetriever(TrainingKnowledgeRetriever):
    def __init__(self) -> None:
        pass

    def retrieve(self, _request):
        raise RuntimeError("simulated unavailable derived index")


class _EmptyRetriever(TrainingKnowledgeRetriever):
    def __init__(self) -> None:
        pass

    def retrieve(self, request):
        del request
        return KnowledgeRetrievalResponse(
            query="fictional empty retrieval",
            results=[],
            limitations=[
                "No knowledge chunks matched the requested filters."
            ],
            index_id="knowledge-" + "0" * 24,
            corpus_root_hash="0" * 64,
        )


@dataclass(frozen=True)
class _Scenario:
    name: str
    intent: AgentIntent
    message: str
    fixture: EvaluationFixture
    knowledge_mode: Literal["configured", "disabled", "unavailable", "empty"]
    provider_mode: Literal["configured", "disabled"]


GatewayFactory = Callable[[Settings], AgentLLMGateway]


class CoachRagSmokeRunner:
    """Run fictional end-to-end Agent scenarios and retain only safe metadata."""

    def __init__(
        self,
        settings: Settings,
        *,
        gateway_factory: GatewayFactory | None = None,
    ) -> None:
        self.settings = settings
        self.gateway_factory = gateway_factory or OpenAICompatibleAgentGateway

    @staticmethod
    def _today_fixture() -> EvaluationFixture:
        source = EVALUATION_FIXTURES["high_fatigue_planned_interval"]
        outputs = deepcopy(source.tool_outputs)
        outputs["get_runner_state"]["risk_level"] = "MODERATE"
        outputs["evaluate_today_workout"]["risk_level"] = "MODERATE"
        return EvaluationFixture(
            name="alpha_today_moderate",
            tool_outputs=outputs,
        )

    @classmethod
    def scenarios(cls) -> list[_Scenario]:
        return [
            _Scenario(
                "GENERAL",
                AgentIntent.GENERAL_TRAINING_QUESTION,
                "阈值训练通常应该怎样安排？",
                EVALUATION_FIXTURES["normal_training"],
                "configured",
                "configured",
            ),
            _Scenario(
                "EXPLAIN",
                AgentIntent.EXPLAIN_RUNNER_STATE,
                "请解释这组完全虚构的 Runner State，并保留数据限制。",
                EVALUATION_FIXTURES["missing_heart_rate"],
                "configured",
                "configured",
            ),
            _Scenario(
                "TODAY",
                AgentIntent.TODAY_RECOMMENDATION,
                "根据虚构计划和状态，我今天应该怎样训练？",
                cls._today_fixture(),
                "configured",
                "configured",
            ),
            _Scenario(
                "PROVIDER_DISABLED",
                AgentIntent.TODAY_RECOMMENDATION,
                "根据虚构计划给出今日训练建议。",
                cls._today_fixture(),
                "disabled",
                "disabled",
            ),
            _Scenario(
                "KNOWLEDGE_INDEX_UNAVAILABLE",
                AgentIntent.TODAY_RECOMMENDATION,
                "知识索引不可用时，保留虚构的确定性今日建议。",
                cls._today_fixture(),
                "unavailable",
                "configured",
            ),
            _Scenario(
                "EMPTY_RETRIEVAL",
                AgentIntent.GENERAL_TRAINING_QUESTION,
                "解释一个当前知识库没有覆盖的虚构训练问题。",
                EVALUATION_FIXTURES["normal_training"],
                "empty",
                "configured",
            ),
        ]

    def _knowledge_tool(
        self,
        mode: Literal["configured", "disabled", "unavailable", "empty"],
    ):
        if mode == "disabled":
            return None
        if mode == "configured":
            return build_configured_knowledge_tool(self.settings)
        if mode == "unavailable":
            return RetrieveTrainingKnowledgeTool(
                _UnavailableRetriever
            )
        return RetrieveTrainingKnowledgeTool(
            _EmptyRetriever
        )

    def _gateway(
        self,
        mode: Literal["configured", "disabled"],
    ) -> AgentLLMGateway:
        if mode == "disabled":
            return _DisabledGateway()
        return self.gateway_factory(self.settings)

    def _run_one(self, scenario: _Scenario) -> SmokeScenarioResult:
        registry = build_evaluation_registry(scenario.fixture)
        knowledge_tool = self._knowledge_tool(scenario.knowledge_mode)
        if knowledge_tool is not None:
            registry.register(knowledge_tool)
        gateway = self._gateway(scenario.provider_mode)
        limits = AgentLimits(max_tool_calls=6)
        agent = GaitLogicCoachAgent(
            gateway=gateway,
            registry=registry,
            context_builder=AgentTrainingContextBuilder(
                registry=registry,
                limits=limits,
                clock=lambda: datetime(
                    2026,
                    7,
                    28,
                    9,
                    0,
                    tzinfo=ZoneInfo("Asia/Shanghai"),
                ),
            ),
            limits=limits,
        )
        request = AgentRequest.for_authenticated_user(
            user_id=900001,
            message=scenario.message,
            intent=scenario.intent,
        )
        started = perf_counter()
        try:
            response = agent.run(request)
        finally:
            close = getattr(gateway, "close", None)
            if callable(close):
                close()
        duration_ms = (perf_counter() - started) * 1000
        context = agent.last_context
        tool_names = (
            [item.tool_name for item in context.tool_results]
            if context is not None
            else []
        )
        failed_tools = (
            [
                item
                for item in context.tool_results
                if item.status != AgentToolStatus.SUCCEEDED
            ]
            if context is not None
            else []
        )
        public_status: Literal["SUCCEEDED", "DEGRADED", "FAILED"]
        provider_status: Literal["SUCCEEDED", "DISABLED", "FAILED"]
        validation_codes = [item.code for item in response.limitations]
        references = response.knowledge_references
        if scenario.provider_mode == "disabled":
            provider_status = "DISABLED"
        elif response.status in {
            AgentRunStatus.SUCCEEDED,
            AgentRunStatus.TOOL_FAILED,
        }:
            provider_status = "SUCCEEDED"
        else:
            provider_status = "FAILED"
        if context is None:
            public_status = "FAILED"
        elif response.status == AgentRunStatus.SUCCEEDED and not failed_tools:
            public_status = "SUCCEEDED"
        else:
            fallback = DeterministicCoachFallback().build(
                intent=scenario.intent,
                message=scenario.message,
                context=context,
                trace=agent.last_trace,
            )
            public_status = "DEGRADED"
            references = []
            validation_codes = [
                *[item.code for item in fallback.warnings],
                *[item.code for item in fallback.limitations],
            ]

        invariance: dict[str, bool] = {}
        if scenario.intent == AgentIntent.TODAY_RECOMMENDATION and context is not None:
            expected = canonical_today_facts_for_fixture(scenario.fixture)
            recommendation = response.today_recommendation
            if public_status == "DEGRADED":
                recommendation = DeterministicCoachFallback().build(
                    intent=scenario.intent,
                    message=scenario.message,
                    context=context,
                ).today_recommendation
            invariance = {
                "decision": bool(
                    recommendation
                    and recommendation.decision == expected["decision"]
                ),
                "planned_workout_status": bool(
                    recommendation
                    and recommendation.planned_workout_status
                    == expected["planned_workout_status"]
                ),
                "risk_level": response.risk_level.value
                == expected["risk_level"]
                if public_status == "SUCCEEDED"
                else bool(
                    recommendation
                    and context.today_evaluation
                    and context.today_evaluation.get("risk_level")
                    == expected["risk_level"]
                ),
                "data_quality": bool(
                    recommendation and recommendation.data_quality == "AVAILABLE"
                ),
            }

        usage_model = getattr(gateway, "last_usage", None)
        usage = (
            usage_model.model_dump(mode="json")
            if isinstance(usage_model, BaseModel)
            else {}
        )
        internal_id_leaked = any(
            item.startswith("knowledge_")
            for item in [reference.document_id for reference in references]
        )
        expected_status = (
            "DEGRADED"
            if scenario.name in {
                "PROVIDER_DISABLED",
                "KNOWLEDGE_INDEX_UNAVAILABLE",
            }
            else "SUCCEEDED"
        )
        expects_references = scenario.name in {"GENERAL", "EXPLAIN", "TODAY"}
        passed = (
            public_status == expected_status
            and not internal_id_leaked
            and (
                len(references) > 0
                if expects_references
                else len(references) == 0
            )
            and (not invariance or all(invariance.values()))
        )
        if scenario.name == "EMPTY_RETRIEVAL":
            passed = (
                public_status in {"SUCCEEDED", "DEGRADED"}
                and not references
                and bool(validation_codes)
            )
        return SmokeScenarioResult(
            scenario=scenario.name,
            intent=scenario.intent,
            status=public_status,
            provider_status=provider_status,
            tool_names=sorted(set(tool_names)),
            knowledge_reference_count=len(references),
            public_document_ids=sorted(
                {item.document_id for item in references}
            ),
            validation_codes=sorted(set(validation_codes)),
            latency_ms=round(duration_ms, 3),
            usage=usage,
            canonical_invariance=invariance,
            passed=passed,
        )

    def run(
        self,
        *,
        business_row_count_before: int = 0,
        business_row_count_after: int = 0,
        residual_database_count: int = 0,
    ) -> CoachRagSmokeReport:
        return CoachRagSmokeReport(
            provider=self.settings.coach_agent_provider,
            chat_model=self.settings.coach_agent_model,
            embedding_model=self.settings.knowledge_embedding_model,
            scenarios=[self._run_one(item) for item in self.scenarios()],
            business_row_count_before=business_row_count_before,
            business_row_count_after=business_row_count_after,
            business_write_count=max(
                0,
                business_row_count_after - business_row_count_before,
            ),
            residual_database_count=residual_database_count,
        )
