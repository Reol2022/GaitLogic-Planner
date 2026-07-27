from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.agent.enums import (
    AgentIntent,
    AgentRiskLevel,
    AgentToolStatus,
)
from server.agent.gateway import MockAgentLLMGateway
from server.agent.knowledge_references import (
    build_knowledge_reference_catalog,
    materialize_knowledge_references,
)
from server.agent.providers.schemas import (
    ProviderAgentModelOutput,
    ProviderTodayModelOutput,
)
from server.agent.registry import AgentToolRegistry
from server.agent.orchestrator import GaitLogicCoachAgent
from server.agent.schemas import (
    AgentContext,
    AgentModelOutput,
    AgentNotice,
    AgentToolResult,
    AgentRequest,
    AgentToolInvocation,
)
from server.agent.tools.knowledge_tools import (
    KnowledgeToolResultItem,
    RetrieveTrainingKnowledgeOutput,
    RetrieveTrainingKnowledgeTool,
)
from server.agent.validator import AgentResponseValidator
from server.agent.today_recommendation import build_authoritative_today_facts
from server.knowledge_retrieval.enums import (
    KnowledgeCategory,
    KnowledgeEvidenceLevel,
)
from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalResponse
from tests.agent_tool_fakes import NOW


def knowledge_output(*, empty: bool = False) -> RetrieveTrainingKnowledgeOutput:
    item = KnowledgeToolResultItem(
        knowledge_reference_id="knowledge_1",
        chunk_id="recovery#principles#001",
        document_id="recovery-principles",
        title="恢复训练原则",
        section="核心原则",
        excerpt="训练刺激只有在能够恢复时才有价值，应根据已有训练事实决定解释强度。",
        category=KnowledgeCategory.RECOVERY,
        source_id="fictional-training-guidance",
        source_title="Fictional Training Guidance",
        knowledge_version="1.0.0",
        evidence_level=KnowledgeEvidenceLevel.SECONDARY,
        score=0.82,
        limitations=[],
    )
    return RetrieveTrainingKnowledgeOutput(
        query_status="EMPTY" if empty else "SUCCEEDED",
        index_id="knowledge-1234567890abcdef12345678",
        corpus_root_hash="a" * 64,
        results=[] if empty else [item],
        limitations=["No matching result."] if empty else [],
    )


def context(
    intent: AgentIntent = AgentIntent.GENERAL_TRAINING_QUESTION,
    *,
    status: AgentToolStatus = AgentToolStatus.SUCCEEDED,
    empty: bool = False,
) -> AgentContext:
    result = AgentToolResult(
        tool_call_id="64ce7fe5-32d2-48cc-9bc0-6c61d2f25c25",
        tool_name="retrieve_training_knowledge",
        status=status,
        data=knowledge_output(empty=empty).model_dump(mode="json")
        if status == AgentToolStatus.SUCCEEDED
        else None,
    )
    return AgentContext(
        request_id="8c785ddb-a652-4fe4-a048-88350c183cc7",
        user_id=4201,
        intent=intent,
        current_time=NOW,
        timezone="Asia/Shanghai",
        runner_state={"overall_state": "UNKNOWN"},
        tool_results=[result],
    )


def final_output(
    intent: AgentIntent = AgentIntent.GENERAL_TRAINING_QUESTION,
    *,
    references: list[str] | None = None,
    answer: str = "Use the retrieved principle as general background.",
    limitations: list[AgentNotice] | None = None,
) -> AgentModelOutput:
    return AgentModelOutput(
        answer=answer,
        summary="General explanation.",
        intent=intent,
        risk_level=AgentRiskLevel.UNKNOWN,
        knowledge_reference_ids=references or [],
        limitations=limitations or [],
    )


def validate(output: AgentModelOutput, agent_context: AgentContext):
    return AgentResponseValidator().validate_model_output(
        output,
        context=agent_context,
        registry=AgentToolRegistry(),
        final=True,
    )


def test_reference_ids_are_strict_for_both_provider_contracts() -> None:
    with pytest.raises(ValidationError):
        ProviderTodayModelOutput(
            answer="safe",
            summary="safe",
            key_evidence_ids=[],
            knowledge_reference_ids=[1],
        )
    with pytest.raises(ValidationError):
        ProviderAgentModelOutput(
            answer="safe",
            intent=AgentIntent.GENERAL_TRAINING_QUESTION,
            knowledge_reference_ids=["Knowledge_1"],
        )
    with pytest.raises(ValidationError):
        ProviderAgentModelOutput(
            answer="safe",
            intent=AgentIntent.GENERAL_TRAINING_QUESTION,
            knowledge_reference_ids=["knowledge_1", "knowledge_1"],
        )


def test_canonical_materialization_hides_internal_fields() -> None:
    references = materialize_knowledge_references(["knowledge_1"], context())
    assert len(references) == 1
    payload = references[0].model_dump(mode="json")
    assert payload["excerpt"].startswith("训练刺激")
    assert "knowledge_reference_id" not in payload
    assert "score" not in payload
    assert "chunk_id" not in payload
    assert "relative_path" not in payload


def test_unknown_reference_and_multiple_catalogs_fail_closed() -> None:
    with pytest.raises(ValueError):
        materialize_knowledge_references(["knowledge_2"], context())
    values = context().model_dump(mode="python")
    values["tool_results"] = [*values["tool_results"], *values["tool_results"]]
    with pytest.raises(ValueError):
        build_knowledge_reference_catalog(AgentContext.model_validate(values))


def test_general_requires_reference_for_successful_non_empty_retrieval() -> None:
    assert not validate(final_output(), context()).valid
    assert validate(
        final_output(references=["knowledge_1"]),
        context(),
    ).valid


def test_failed_or_empty_retrieval_requires_limitation_and_forbids_reference() -> None:
    limitation = [AgentNotice(code="KNOWLEDGE_UNAVAILABLE", message="Knowledge unavailable.")]
    failed_context = context(status=AgentToolStatus.FAILED)
    assert not validate(
        final_output(references=["knowledge_1"], limitations=limitation),
        failed_context,
    ).valid
    assert validate(
        final_output(limitations=limitation),
        failed_context,
    ).valid
    empty_context = context(empty=True)
    assert not validate(final_output(), empty_context).valid
    assert validate(final_output(limitations=limitation), empty_context).valid


def test_unretrieved_knowledge_claim_and_fabricated_source_are_rejected() -> None:
    no_retrieval = AgentContext(
        request_id="8c785ddb-a652-4fe4-a048-88350c183cc7",
        user_id=4202,
        intent=AgentIntent.GENERAL_TRAINING_QUESTION,
        current_time=NOW,
        timezone="Asia/Shanghai",
    )
    assert not validate(
        final_output(answer="根据训练知识库，这样安排更合适。"),
        no_retrieval,
    ).valid
    assert not validate(
        final_output(
            references=["knowledge_1"],
            answer="某项研究表明这一定有效。",
        ),
        context(),
    ).valid


def test_exact_excerpt_and_general_personal_fact_are_rejected() -> None:
    excerpt = knowledge_output().results[0].excerpt
    assert not validate(
        final_output(references=["knowledge_1"], answer=excerpt),
        context(),
    ).valid
    assert not validate(
        final_output(
            references=["knowledge_1"],
            answer="你当前训练状态显示疲劳较高。",
        ),
        context(),
    ).valid


def test_explain_runner_state_cannot_invent_personal_distance() -> None:
    explain_context = context(AgentIntent.EXPLAIN_RUNNER_STATE)
    assert not validate(
        final_output(
            AgentIntent.EXPLAIN_RUNNER_STATE,
            references=["knowledge_1"],
            answer="你最近训练了 42 公里。",
        ),
        explain_context,
    ).valid


def test_today_knowledge_cannot_override_deterministic_fields() -> None:
    values = context(AgentIntent.TODAY_RECOMMENDATION).model_dump(mode="python")
    values.update(
        {
            "today_workout": {"workout_status": "PLANNED"},
            "today_evaluation": {
                "data_status": "AVAILABLE",
                "decision": "passed",
                "risk_level": "LOW",
                "evidence": ["fictional_metric"],
            },
            "data_quality": {"data_status": "AVAILABLE"},
        }
    )
    today_context = AgentContext.model_validate(values)
    facts = build_authoritative_today_facts(
        today_context,
        user_message="今天怎么训练？",
        key_evidence=["fictional_metric"],
    )
    safe = AgentModelOutput(
        answer="知识只用于解释既有结论。",
        summary="按既有结论执行。",
        intent=AgentIntent.TODAY_RECOMMENDATION,
        risk_level=facts.risk_level,
        warnings=facts.warnings,
        limitations=facts.limitations,
        knowledge_reference_ids=["knowledge_1"],
        today_recommendation=facts.recommendation,
    )
    assert validate(safe, today_context).valid
    unsafe = safe.model_copy(
        update={
            "risk_level": AgentRiskLevel.HIGH,
            "today_recommendation": safe.today_recommendation.model_copy(
                update={"decision": "REST_OR_RECOVERY"}
            ),
        }
    )
    assert not validate(unsafe, today_context).valid


class StaticRetriever:
    def retrieve(self, request):
        output = knowledge_output()
        item = output.results[0]
        from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalResult

        return KnowledgeRetrievalResponse(
            query=request.query,
            results=[
                KnowledgeRetrievalResult(
                    rank=1,
                    score=item.score,
                    chunk_id=item.chunk_id,
                    document_id=item.document_id,
                    title=item.title,
                    section=item.section,
                    excerpt=item.excerpt,
                    category=item.category,
                    tags=["recovery"],
                    source_id=item.source_id,
                    source_title=item.source_title,
                    knowledge_version=item.knowledge_version,
                    evidence_level=item.evidence_level,
                    relative_path="documents/recovery-principles.md",
                    limitations=[],
                )
            ],
            limitations=[],
            index_id=output.index_id,
            corpus_root_hash=output.corpus_root_hash,
        )


def test_orchestrator_materializes_only_public_canonical_reference() -> None:
    call = AgentToolInvocation(
        tool_name="retrieve_training_knowledge",
        arguments={"query": "恢复训练的一般原则"},
    )
    gateway = MockAgentLLMGateway(
        [
            AgentModelOutput(
                intent=AgentIntent.GENERAL_TRAINING_QUESTION,
                tool_calls=[call],
            ),
            final_output(references=["knowledge_1"]),
        ]
    )
    registry = AgentToolRegistry()
    registry.register(
        RetrieveTrainingKnowledgeTool(lambda: StaticRetriever())
    )
    response = GaitLogicCoachAgent(
        gateway=gateway,
        registry=registry,
    ).run(
        AgentRequest(
            user_id=4203,
            message="恢复训练的一般原则是什么？",
            intent=AgentIntent.GENERAL_TRAINING_QUESTION,
        )
    )
    assert response.status.value == "SUCCEEDED"
    assert len(response.knowledge_references) == 1
    public = response.knowledge_references[0].model_dump(mode="json")
    assert public["document_id"] == "recovery-principles"
    assert "knowledge_reference_id" not in public
    assert "score" not in public
